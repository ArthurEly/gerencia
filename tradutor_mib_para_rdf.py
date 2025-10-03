import os
from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import RDF, RDFS
from pysnmp.smi import builder, view, error

# LINHA REMOVIDA: A importação problemática foi removida daqui.
# from pysnmp.smi.rfc1902 import MibScalar, MibTableColumn

def mib_para_rdf(mib_source_path, mib_modules):
    """
    Traduz módulos MIB para RDF, extraindo o máximo de detalhes possível,
    incluindo acesso, status e valores enumerados.
    """
    g = Graph()
    MIBO = Namespace("http://purl.org/net/mibo#")
    g.bind("mibo", MIBO)
    g.bind("rdfs", RDFS)

    mib_builder = builder.MibBuilder()
    try:
        mib_builder.add_mib_sources(builder.DirMibSource(mib_source_path))
        print(f"-> Diretório de MIBs '{mib_source_path}' adicionado com sucesso.")
    except error.SmiError as e:
        print(f"Erro ao adicionar diretório de MIBs: {e}")
        return None

    try:
        mib_builder.load_modules(*mib_modules)
        print(f"-> Módulos {', '.join(mib_modules)} carregados com sucesso.")
    except error.SmiError as e:
        print(f"Erro ao carregar os módulos MIB: {e}")
        return g

    # CORREÇÃO APLICADA: Obtemos as classes dinamicamente do MIB Builder.
    MibScalar, MibTableColumn = mib_builder.importSymbols(
        'SNMPv2-SMI', 'MibScalar', 'MibTableColumn'
    )

    print("\nIniciando a tradução para RDF...")
    
    for module_name in mib_modules:
        module = mib_builder.mibSymbols.get(module_name, {})
        for symbol_name, symbol_obj in module.items():

            if not isinstance(symbol_obj, (MibScalar, MibTableColumn)):
                continue

            subject = MIBO[symbol_name]
            g.add((subject, RDF.type, MIBO.MibObject))
            g.add((subject, RDFS.label, Literal(symbol_name)))

            if hasattr(symbol_obj, 'name'):
                oid = '.'.join(map(str, symbol_obj.name))
                g.add((subject, MIBO.hasOID, Literal(oid)))

            if hasattr(symbol_obj, 'description') and symbol_obj.description:
                g.add((subject, RDFS.comment, Literal(str(symbol_obj.description))))

            if hasattr(symbol_obj, 'syntax') and symbol_obj.syntax is not None:
                try:
                    syntax_str = symbol_obj.syntax.__class__.__name__
                    g.add((subject, MIBO.hasSyntax, Literal(syntax_str)))
                except Exception as e:
                    print(f"  - AVISO: Não foi possível processar a syntax para {symbol_name}. Erro: {e}")
            
            if hasattr(symbol_obj, 'maxAccess'):
                access = str(symbol_obj.maxAccess)
                g.add((subject, MIBO.hasMaxAccess, Literal(access)))

            if hasattr(symbol_obj, 'status'):
                status = str(symbol_obj.status)
                g.add((subject, MIBO.hasStatus, Literal(status)))

            if hasattr(symbol_obj.syntax, 'namedValues'):
                for name, value in symbol_obj.syntax.namedValues.items():
                    b_node = BNode()
                    g.add((subject, MIBO.hasEnumeration, b_node))
                    g.add((b_node, MIBO.hasName, Literal(name)))
                    g.add((b_node, MIBO.hasValue, Literal(value)))
            
            print(f"  - Processado: {symbol_name}")

    print("\nTradução concluída.")
    return g


if __name__ == "__main__":
    mib_directory = "mibs_compilados"
    modules_to_translate = ['IF-MIB', 'SNMPv2-MIB'] 

    knowledge_graph = mib_para_rdf(mib_directory, modules_to_translate)

    if knowledge_graph:
        output_file = "knowledge_graph.ttl"
        try:
            knowledge_graph.serialize(destination=output_file, format="turtle")
            print(f"\nGrafo salvo em '{output_file}'.")
            print(f"Total de triplas RDF: {len(knowledge_graph)}")
        except Exception as e:
            print(f"Erro ao salvar o RDF: {e}")