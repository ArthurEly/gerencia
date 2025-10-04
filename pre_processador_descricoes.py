import re
import json

def extrair_descricoes(mib_files):
    """
    Lê arquivos de texto MIB (.my) e extrai os nomes dos objetos
    e suas descrições usando expressões regulares.
    """
    all_descriptions = {}
    # Expressão regular para encontrar um nome de objeto (ex: sysDescr) seguido de uma cláusula DESCRIPTION
    # re.DOTALL faz o '.' incluir novas linhas, para capturar descrições de múltiplas linhas
    # re.MULTILINE faz o '^' funcionar no início de cada linha
    regex = re.compile(
        r"^\s*([\w-]+)\s+(?:OBJECT-TYPE|OBJECT-GROUP|NOTIFICATION-TYPE|MODULE-IDENTITY)\s*.*?DESCRIPTION\s*\"(.+?)\"",
        re.DOTALL | re.MULTILINE
    )

    for file_path in mib_files:
        try:
            print(f"Processando arquivo de texto MIB: '{file_path}'")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                matches = regex.finditer(content)
                count = 0
                for match in matches:
                    name = match.group(1).strip()
                    # Limpa a descrição removendo novas linhas e espaços excessivos
                    desc = match.group(2).strip()
                    desc_cleaned = re.sub(r'\s+', ' ', desc)
                    all_descriptions[name] = desc_cleaned
                    count += 1
                print(f"  -> Encontradas {count} descrições.")
        except FileNotFoundError:
            print(f"!! AVISO: Arquivo MIB de texto '{file_path}' não encontrado. Pulando.")
            
    return all_descriptions

if __name__ == "__main__":
    # IMPORTANTE: Coloque aqui os nomes dos seus arquivos MIB originais (.my)
    # Você precisa ter esses arquivos de texto na sua pasta
    mib_files_to_process = ['mibs/SNMPv2-MIB.my', 'mibs/IF-MIB.my'] 
    output_json_file = 'descricoes_consolidadas.json'
    
    descriptions = extrair_descricoes(mib_files_to_process)
    
    with open(output_json_file, 'w', encoding='utf-8') as f:
        json.dump(descriptions, f, indent=4, ensure_ascii=False)
        
    print(f"\nExtração concluída. Descrições salvas em '{output_json_file}'.")
    print(f"Total de {len(descriptions)} descrições únicas encontradas.")