import random
import requests

class OTPService:
    WEBHOOK_URL = "https://automation-n8n.v4riem.easypanel.host/webhook/roletacodconfirmacao"

    @staticmethod
    def gerar_codigo() -> str:
        """Gera um OTP aleatório de 6 dígitos."""
        return str(random.randint(100000, 999999))
        
    @staticmethod
    def enviar_otp_whatsapp(cpf: str, telefone: str, codigo: str) -> bool:
        """
        Dispara o payload pro Endpoint n8n que mandará o SMS/Whatsapp
        Retorna (sucesso, error_msg)
        """
        payload = {
            'cpf': cpf,
            'telefone': telefone,
            'codigo': codigo
        }
        
        try:
            response = requests.post(OTPService.WEBHOOK_URL, data=payload, timeout=10)
            if response.status_code == 200:
                return True, "Enviado com sucesso"
            return False, f"Falha na API: {response.text}"
        except Exception as e:
            return False, str(e)

