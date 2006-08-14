import pydmc.simpletest

module_names = ['abstractplot', 'count', 'datafile', 'numeric', 'plot',
                'shelltools']
module_names = [ 'pydmc.' + mn for mn in module_names ]

pydmc.simpletest.main(module_names)


