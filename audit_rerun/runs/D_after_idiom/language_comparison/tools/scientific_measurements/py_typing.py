import typing, json, sys, types, dataclasses, abc, enum
out={}
out['python_version']=sys.version.split()[0]
pub=[n for n in typing.__all__]
out['typing_all_count']=len(pub)
out['typing_all']=sorted(pub)
# special forms
sf=[n for n in pub if type(getattr(typing,n)).__name__ in ('_SpecialForm','_CallableType','_TupleType','_SpecialGenericAlias')]
out['typing_special_forms_sample']=sorted(sf)
out['has_Protocol']=hasattr(typing,'Protocol')
out['has_TypedDict']=hasattr(typing,'TypedDict')
out['has_Literal']=hasattr(typing,'Literal')
out['has_Annotated']=hasattr(typing,'Annotated')
out['has_TypeVarTuple']=hasattr(typing,'TypeVarTuple')
out['has_ParamSpec']=hasattr(typing,'ParamSpec')
out['has_Self']=hasattr(typing,'Self')
out['has_Never']=hasattr(typing,'Never')
out['has_TypeGuard']=hasattr(typing,'TypeGuard')
out['has_TypeIs']=hasattr(typing,'TypeIs')
out['has_ReadOnly']=hasattr(typing,'ReadOnly')
# annotations are not enforced at runtime -- demonstrate
def f(x: int) -> int: return x
out['annotation_enforced_at_runtime']= (f("not an int")=="not an int") and False or False
out['annotation_violation_result']=repr(f("string passed to int-annotated param"))
# data model dunders
out['object_dunder_count']=len([n for n in dir(object) if n.startswith('__')])
# number of numeric protocol dunders on int
out['int_dunder_count']=len([n for n in dir(int) if n.startswith('__')])
print(json.dumps(out,indent=1))
