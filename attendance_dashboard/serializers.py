from rest_framework import serializers

class EncryptedPayloadSerializer(serializers.Serializer):
    mac_address = serializers.CharField(max_length=17, required=True, help_text="MAC address of the Gateway Device")
    encrypted_data = serializers.CharField(required=True, help_text="AES encrypted attendance data payload")
    iv = serializers.CharField(required=True, help_text="Initialization Vector for AES decryption base64 encoded")
    nonce = serializers.CharField(required=True, help_text="Nonce from handshake to identify session")
    timestamp = serializers.FloatField(required=True, help_text="Unix timestamp of the request to prevent replay attacks")
