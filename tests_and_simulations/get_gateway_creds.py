import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from attendance_dashboard.models import GatewayDevice # noqa: E402
pi, _ = GatewayDevice.objects.get_or_create(
    mac_address="B8:27:EB:AA:BB:CC",
    defaults={"name": "Raspberry Pi Edge"}
)
print("API_KEY=" + str(pi.api_key))
