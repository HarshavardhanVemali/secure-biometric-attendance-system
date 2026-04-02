from django.utils import timezone
from datetime import timedelta
from .models import AttendanceLog, StudentAnalytics

def calculate_performance_score(employee):
    """
    Calculates a Success Score (0-100) based on:
    1. Punctuality (Weight: 40%): logs before 09:05 AM.
    2. Consistency (Weight: 60%): attendance frequency in last 30 days.
    """
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    
    logs = AttendanceLog.objects.filter(
        employee=employee, 
        timestamp__gte=thirty_days_ago,
        punch_type="Check-in"
    )
    
    total_punches = logs.count()
    if total_punches == 0:
        score = 50 # Baseline for new/inactive
        punctuality = 100
        consistency = 0
    else:
        # 1. Punctuality Calculation
        on_time_count = 0
        for log in logs:
            # Check if punch was before 09:05 AM (local time)
            # We assume the server is set to the correct timezone
            log_time = log.timestamp.time()
            if log_time.hour < 9 or (log_time.hour == 9 and log_time.minute <= 5):
                on_time_count += 1
        
        punctuality = (on_time_count / total_punches) * 100
        
        # 2. Consistency Calculation (Assume 22 working days in 30 days)
        consistency = (total_punches / 22) * 100
        if consistency > 100:
            consistency = 100
            
        # Weighted Score
        score = (punctuality * 0.4) + (consistency * 0.6)

    # 3. Determine Risk Level (Base calculation, potentially overridden by Ollama)
    risk = 'LOW'
    if score < 40:
        risk = 'HIGH'
    elif score < 70:
        risk = 'MEDIUM'
        
    advisory = ""

    # 4. Ollama Local LLM Integration
    import requests
    import json
    
    try:
        ollama_url = "http://localhost:11434/api/generate"
        prompt = f"""
        Analyze the attendance metrics for this employee:
        - Punctuality: {punctuality}% (on time before 9:05 AM)
        - Consistency: {consistency}% (present days out of expected)
        - Calculated Success Score: {score}/100

        Based on these metrics, provide a strict security and reliability assessment.
        Respond ONLY with a JSON object in this exact format:
        {{"risk_level": "LOW" or "MEDIUM" or "HIGH", "advisory": "A 1-2 sentence system advisory explaining the risk."}}
        """
        
        response = requests.post(ollama_url, json={
            "model": "llama3.2:1b",
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }, timeout=15)
        
        if response.status_code == 200:
            raw_response = response.json().get("response", "{}").strip()
            # Strip potential markdown code blocks if the model hallucinates them
            if raw_response.startswith("```json"):
                raw_response = raw_response[7:]
            if raw_response.startswith("```"):
                raw_response = raw_response[3:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3]
                
            ai_data = json.loads(raw_response.strip())
            if "risk_level" in ai_data and ai_data["risk_level"] in ['LOW', 'MEDIUM', 'HIGH']:
                risk = ai_data["risk_level"]
            if "advisory" in ai_data:
                advisory = ai_data["advisory"].upper()
    except Exception as e:
        # Graceful fallback if Ollama is offline or times out
        print(f"[Ollama Error]: {e}")
        advisory = "[SYSTEM FALLBACK] AI ENGINE OFFLINE. DEFAULTING TO STATISTICAL HEURISTICS."

    # Update or Create Analytics Record
    analytics, _ = StudentAnalytics.objects.update_or_create(
        employee=employee,
        defaults={
            'success_score': int(score),
            'punctuality_rate': round(punctuality, 1),
            'attendance_consistency': round(consistency, 1),
            'risk_level': risk,
            # We can store advisory later if we add a field, but for now we'll 
            # calculate it on the fly or pass it in context if we just need it globally.
            # Currently storing the basic fields to match models.py
        }
    )
    
    # Attach advisory to the returned object dynamically so it can be used in views
    analytics.ai_advisory = advisory
    
    return analytics