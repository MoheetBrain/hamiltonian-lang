import json, sympy, inspect, pkgutil, importlib, sys, warnings
warnings.filterwarnings('ignore')
out={'sympy_version':sympy.__version__,'python':sys.version.split()[0]}
from sympy.core.basic import Basic
from sympy.core.function import Function, AppliedUndef
from sympy.core.expr import Expr

def all_subclasses(c):
    s=set()
    stack=[c]
    while stack:
        k=stack.pop()
        for sub in k.__subclasses__():
            if sub not in s:
                s.add(sub); stack.append(sub)
    return s

# Import the whole documented public surface first so subclasses are registered.
mods=['sympy','sympy.functions','sympy.functions.special.bessel','sympy.functions.special.polynomials',
 'sympy.stats','sympy.physics.units','sympy.combinatorics','sympy.geometry','sympy.logic',
 'sympy.matrices','sympy.polys','sympy.ntheory','sympy.series','sympy.integrals','sympy.solvers',
 'sympy.assumptions','sympy.tensor','sympy.vector','sympy.sets','sympy.categories','sympy.diffgeom',
 'sympy.holonomic','sympy.calculus','sympy.crypto','sympy.codegen','sympy.printing','sympy.simplify',
 'sympy.concrete','sympy.discrete','sympy.plotting','sympy.algebras','sympy.liealgebras']
loaded=[]
for m in mods:
    try:
        importlib.import_module(m); loaded.append(m)
    except Exception as e:
        pass
out['modules_imported_for_subclass_registration']=loaded

basic_subs=all_subclasses(Basic)
out['Basic_subclasses_total_after_imports']={'value':len(basic_subs)}
expr_subs=all_subclasses(Expr)
out['Expr_subclasses_total']=len(expr_subs)
func_subs=all_subclasses(Function)
out['Function_subclasses_total']=len(func_subs)
# concrete named math functions: subclasses of Function defined under sympy.functions
mathfn=sorted({c.__name__ for c in func_subs if c.__module__.startswith('sympy.functions')})
out['Function_subclasses_under_sympy_functions_count']=len(mathfn)
out['Function_subclasses_under_sympy_functions']=mathfn
# public names in the top-level sympy namespace
pub=[n for n in dir(sympy) if not n.startswith('_')]
out['sympy_toplevel_public_names']=len(pub)
callable_pub=[n for n in pub if callable(getattr(sympy,n))]
out['sympy_toplevel_public_callables']=len(callable_pub)
# names in sympy that are Function subclasses (the "built-in math function" inventory as exported)
exported_funcs=sorted(n for n in pub if isinstance(getattr(sympy,n),type) and issubclass(getattr(sympy,n),Function))
out['sympy_toplevel_exported_Function_classes_count']=len(exported_funcs)
out['sympy_toplevel_exported_Function_classes']=exported_funcs
# Atoms / singletons
from sympy.core.singleton import S
sing=[n for n in dir(S) if not n.startswith('_')]
out['S_singleton_registry_count']=len(sing)
out['S_singleton_registry']=sorted(sing)
print(json.dumps(out,indent=1))
