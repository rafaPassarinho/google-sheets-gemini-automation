from google import genai
import json
import os
from dotenv import load_dotenv
from utils import get_today_str_iso

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

MODEL_NAME = "gemini-2.5-flash-lite"

def parse_audio_expense(audio_path: str) -> dict:
    """
    Transcreve o áudio e retorna um dict:
    {
      "tipo": "receita" | "despesa_fixa" | "despesa_diaria" | "economia",
      "valor": float,
      "categoria": str,
      "data": "YYYY-MM-DD",
      "descricao": str
    }

    args:
        audio_path (str): caminho para o arquivo de áudio a ser processado.
    returns:
        dict: dicionário com as informações extraídas do áudio.
    raises:
        ValueError: se a resposta do modelo não for um JSON válido ou faltar campos essenciais.
    """
    # instruções claras para o modelo
    prompt = f"""
    Você é um assistente financeiro que classifica gastos e receitas.

    REGRAS PARA TIPOS:
    - "receita": dinheiro que entra (salário, reembolso, rendimentos, etc.).
    - "despesa_fixa": contas mensais ou recorrentes (energia, água, gás, condomínio, aluguel, wifi, telefone, cartão de crédito, seguro, etc.).
    - "despesa_diaria": gastos do dia a dia (mercado, restaurante, lanchonete, combustível, transporte, farmácia, bar, lazer, etc.).
    - "economia": quando guardar dinheiro na caixinha/poupança/economia (ex: "guardei 100 na caixinha", "economizei 50 reais", "poupança de 200").

    **CASO ESPECIAL - SEM GASTOS:**
    Se o usuário disser que NÃO gastou nada, retorne:
    - tipo: "despesa_diaria"
    - valor: 0.0
    - categoria: "nenhum"
    - descricao: "Sem gastos"

    Exemplos:
    - "Gastei 50 reais de energia" -> tipo = "despesa_fixa"
    - "Gastei 20 reais no mercado" -> tipo = "despesa_diaria"
    - "Recebi 500 de salário" -> tipo = "receita"
    - "Guardei 100 na caixinha" -> tipo = "economia"
    - "Economizei 50 reais hoje" -> tipo = "economia"
    - "Coloquei 200 na poupança" -> tipo = "economia"
    - "Hoje não gastei nada" -> tipo = "despesa_diaria", valor = 0.0

    CAMPO DATA:
    - Se o áudio falar "hoje", "agora" ou não falar data, use "{get_today_str_iso()}".
    - Se mencionar explicitamente uma data (ex: "dia 10", "10 de fevereiro"), converta para o formato "YYYY-MM-DD" correto.

    FORMATO DE RESPOSTA:
    Responda APENAS com um JSON válido, sem texto extra, no formato:

    {{
      "tipo": "receita" | "despesa_fixa" | "despesa_diaria" | "economia",
      "valor": 13.8,
      "categoria": "mercado",
      "data": "YYYY-MM-DD",
      "descricao": "Gasto no mercado"
    }}
    """
    audio_file = client.files.upload(file=audio_path)
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, audio_file],
            config={
                "response_mime_type": "application/json"
            }
        )

        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()  # remove ```json ... ```
        elif text.startswith("```"):
            text = text[3:-3].strip()  # remove ``` ... ```
        
        data = json.loads(text)

        # normalização/validações
        data["valor"] = float(data["valor"])
        
        if not data.get("tipo"):
            # fallback: tudo que não for receita vira despesa_diaria
            data["tipo"] = "despesa_diaria"

        if data["tipo"] not in ["receita", "despesa_fixa", "despesa_diaria", "economia"]:
            data["tipo"] = "despesa_diaria"

        if not data.get("data"):
            data["data"] = get_today_str_iso()
        
        if not data.get("descricao"):
            if data["valor"] == 0.0:
                data["descricao"] = "Sem gastos"
            else:
                data["descricao"] = f"{data['tipo']} de {data['valor']}"
        
        if not data.get("categoria"):
            if data["valor"] == 0.0:
                data["categoria"] = "nenhum"
            elif data["tipo"] == "economia":
                data["categoria"] = "poupança"
            else:
                data["categoria"] = "outros"

        return data
    
    except json.JSONDecodeError:
        raise ValueError(f"Resposta do modelo não é um JSON válido: {response.text}")
    finally:
        try:
            client.files.delete(name=audio_file.name)
        except Exception as e:
            print(f"Erro ao deletar arquivo do modelo: {e}")