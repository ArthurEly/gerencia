# Source - https://stackoverflow.com/a
# Posted by Sweet Burlap
# Retrieved 2025-11-09, License - CC BY-SA 3.0

filename = "./grafo_IF-MIB.ttl" #replace with something interesting
uri = "uri_of_interest" #replace with something interesting

import rdflib

rdflib.plugin.register('sparql', rdflib.query.Processor, 
                        'rdfextras.sparql.query', 'SPARQLQueryResult')
rdflib.plugin.register('sparql', rdflib.query.Result,
                       'rdfextras.sparql.query', 'SPARQLQueryResult')

g=rdflib.Graph()
g.parse(filename)

#results = g.query()
