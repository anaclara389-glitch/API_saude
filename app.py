from pprint import pprint
import requests


menu = """ AÇÃO QUE DESEJA REALIZAR:
1 - DADOS SOBRE ARBOVIROSES
2 - ASSISTENCIA À SAÚDE"""

print(menu)
escolha = input("Digite o que você deseja buscar: ")

categoria = ""
subcategoria = ""

if escolha == "1": #------------------
    categoria = "arboviroses"

    
    menu_amb = """NOTIFICAÇÕES SOBRE ARBOVIROSES DISPONÍVEIS:
    1 - zikavirus
    2 - dengue"""
    print(menu_amb)

    escolha2 = input("Digite a opção desejada (1 ou 2): ")#----------------

    if escolha2 == "1":
        subcategoria = "zikavirus"
    elif escolha2 == "2":
        subcategoria = "dengue"
    else:
        print("Doença não encontrada")

elif escolha == "2":#------------------
    categoria = "assistencia-a-saude"

    menu_as = """ASSISTÊNCIAS DISPONÍVEIS:
    1 - hospitais-e-leitos
    2 - unidades-basicas-de-saude"""
    print(menu_as)

    escolha2 = input("Digite a opção desejada (1 ou 2): ")#--------------------

    if escolha2 == "1":
        subcategoria = "hospitais-e-leitos"
    elif escolha2 == "2":
        subcategoria = "unidade-basicas-de-saude"
    else:
        print("Assistência não encontrada")

#------------------------------------------------------------------------------------------------

def consultar_catalogo(categoria, subcategoria):
    if not categoria or not subcategoria:
        print("\nNão foi possível consultar: opção inválida selecionada.")
        return

    url = f"https://apidadosabertos.saude.gov.br/{categoria}/{subcategoria}"
    print(f"\nConsultando: {url}\n")

    resposta = requests.get(url)

    if resposta.status_code == 200:
        dados_api = resposta.json()
        pprint(dados_api)
    else:
        print(f"Algo deu errado: {resposta.status_code}")


consultar_catalogo(categoria, subcategoria)