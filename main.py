from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import openai
from PyPDF2 import PdfReader
import os
import re

app = FastAPI(title="Income Proof Verification API", description="API para avaliar comprovantes de renda.", version="1.0.0")

# Configuração da chave de API
OPENAI_API_KEY = "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"
if not OPENAI_API_KEY:
    raise ValueError("A chave da API OpenAI não está configurada. Defina a variável de ambiente 'OPENAI_API_KEY'.")
openai.api_key = OPENAI_API_KEY

def process_income_proof(file_content: str, expected_name: str):
    """
    Avalia o texto de um comprovante de renda e identifica se é válido, qual a renda e o nome.

    :param file_content: Conteúdo textual do documento.
    :param expected_name: Nome esperado para validação.
    :return: Dicionário com as informações analisadas.
    """
    # Prompt para a API
    prompt = f"""
Você é um assistente que avalia comprovantes de renda. Analise o seguinte texto e responda:
1. O documento é um comprovante de renda válido? Justifique brevemente.
2. Qual é o valor da renda identificado no documento?
3. Qual é o nome completo da pessoa associada ao comprovante?

Texto do documento:
{file_content}
"""

    # Fazer a chamada à API
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",  # Substitua pelo modelo apropriado
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em análise de documentos financeiros."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.2
        )

        # Extrair a resposta
        result = response["choices"][0]["message"]["content"].strip()

        # Processar a resposta em um formato JSON adequado
        lines = result.split("\n")
        is_valid = any("sim" in line.lower() or "valido" in line.lower() for line in lines if "comprovante de renda" in line.lower())

        # Extração do valor da renda como número
        income_match = re.search(r"R\$\s?([\d,.]+)", result)
        income = float(income_match.group(1).replace(".", "").replace(",", ".")) if income_match else None

        # Extração do nome detectado
        detected_name_match = re.search(r"nome completo.*?é\s*(.*?)(\.|\n|$)", result, re.IGNORECASE)
        detected_name = detected_name_match.group(1).strip() if detected_name_match else None

        # Comparação do nome
        name_matches = detected_name and expected_name.lower() in detected_name.lower()

        # Texto de resposta para o usuário final
        response_text = (
            "O documento enviado foi validado com sucesso. Todos os dados estão corretos."
            if is_valid else
            "O documento enviado não é válido. Por favor, insira um comprovante de renda válido."
        )

        # Justificativa limpa para o campo details
        justification = "\n".join(
            line.strip() for line in lines if not line.startswith("1.") and not line.startswith("2.") and not line.startswith("3.")
        )

        return {
            "is_valid": is_valid,
            "income": income,
            "detected_name": detected_name,
            "name_matches": name_matches,
            "details": justification,
            "response_text": response_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar o arquivo: {e}")

@app.post("/analyze", summary="Analisar Comprovante de Renda")
async def analyze_income_proof(file: UploadFile = File(...), name: str = None):
    """
    Endpoint para avaliar um comprovante de renda e identificar a renda.

    :param file: Arquivo enviado pelo usuário (.txt ou .pdf).
    :param name: Nome esperado para validação.
    :return: JSON com resultado da análise.
    """
    # Verificar tipo de arquivo
    if not (file.filename.endswith(".txt") or file.filename.endswith(".pdf")):
        raise HTTPException(status_code=400, detail="Formato de arquivo não suportado. Use .txt ou .pdf.")

    # Ler o conteúdo do arquivo
    try:
        if file.filename.endswith(".txt"):
            content = (await file.read()).decode("utf-8")
        elif file.filename.endswith(".pdf"):
            reader = PdfReader(file.file)
            content = "\n".join(page.extract_text() for page in reader.pages)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler o arquivo: {e}")

    if not name:
        raise HTTPException(status_code=400, detail="O parâmetro 'name' é obrigatório.")

    # Processar o conteúdo
    analysis = process_income_proof(content, name)

    # Retornar o resultado
    return JSONResponse(content=analysis)
