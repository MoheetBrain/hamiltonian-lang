import sys, keyword, ast, builtins, json, inspect, token, tokenize, operator
out={}
out['python_version']=sys.version
out['hard_keywords_count']=len(keyword.kwlist)
out['hard_keywords']=keyword.kwlist
out['soft_keywords_count']=len(keyword.softkwlist)
out['soft_keywords']=keyword.softkwlist
# ast nodes
nodes=[n for n in dir(ast) if isinstance(getattr(ast,n),type) and issubclass(getattr(ast,n),ast.AST)]
out['ast_all_AST_subclasses_incl_abstract']=len(nodes)
# concrete: those with _fields defined and not abstract bases
abstract={'AST','mod','stmt','expr','expr_context','boolop','operator','unaryop','cmpop','comprehension',
 'excepthandler','arguments','arg','keyword','alias','withitem','match_case','pattern','type_ignore','type_param','slice'}
concrete=[n for n in nodes if n not in ('AST',)]
out['ast_node_names_sorted']=sorted(nodes)
# direct subclasses of ast.AST = the top-level abstract categories
direct=[n for n in nodes if getattr(ast,n).__bases__==(ast.AST,)]
out['ast_direct_AST_subclasses']=sorted(direct)
out['ast_direct_AST_subclasses_count']=len(direct)
# leaf classes (no subclasses among the set)
allc={getattr(ast,n) for n in nodes}
leaves=[n for n in nodes if not any(c is not getattr(ast,n) and issubclass(c,getattr(ast,n)) for c in allc)]
out['ast_leaf_classes_count']=len(leaves)
out['ast_leaf_classes']=sorted(leaves)
# deprecated aliases present in 3.12+: Num, Str, Bytes, NameConstant, Ellipsis
depr=[n for n in nodes if n in ('Num','Str','Bytes','NameConstant','Ellipsis','Index','ExtSlice','AugLoad','AugStore','Param','Suite')]
out['ast_deprecated_aliases_present']=sorted(depr)
# stmt / expr subclasses
out['ast_stmt_subclasses_count']=len([n for n in nodes if issubclass(getattr(ast,n),ast.stmt)])
out['ast_stmt_subclasses']=sorted(n for n in nodes if issubclass(getattr(ast,n),ast.stmt))
out['ast_expr_subclasses_count']=len([n for n in nodes if issubclass(getattr(ast,n),ast.expr)])
out['ast_expr_subclasses']=sorted(n for n in nodes if issubclass(getattr(ast,n),ast.expr))
out['ast_operator_binop_count']=len([n for n in nodes if issubclass(getattr(ast,n),ast.operator) and n!='operator'])
out['ast_operator_binops']=sorted(n for n in nodes if issubclass(getattr(ast,n),ast.operator) and n!='operator')
out['ast_unaryop_count']=len([n for n in nodes if issubclass(getattr(ast,n),ast.unaryop) and n!='unaryop'])
out['ast_cmpop_count']=len([n for n in nodes if issubclass(getattr(ast,n),ast.cmpop) and n!='cmpop'])
out['ast_cmpops']=sorted(n for n in nodes if issubclass(getattr(ast,n),ast.cmpop) and n!='cmpop')
out['ast_pattern_count']=len([n for n in nodes if issubclass(getattr(ast,n),ast.pattern) and n!='pattern'])
# builtins
bi=[n for n in dir(builtins) if not n.startswith('_')]
out['builtins_total_public']=len(bi)
excs=[n for n in bi if isinstance(getattr(builtins,n),type) and issubclass(getattr(builtins,n),BaseException)]
out['builtin_exceptions_count']=len(excs)
funcs=[n for n in bi if inspect.isbuiltin(getattr(builtins,n)) or (callable(getattr(builtins,n)) and not isinstance(getattr(builtins,n),type))]
out['builtin_functions_count']=len(funcs)
types_=[n for n in bi if isinstance(getattr(builtins,n),type) and n not in excs]
out['builtin_types_count']=len(types_)
out['builtin_types']=sorted(types_)
# tokens
out['token_exact_types_count']=len(token.EXACT_TOKEN_TYPES)
out['token_exact_types']=sorted(token.EXACT_TOKEN_TYPES.keys())
# dunder operator protocol methods
out['operator_module_dunder_count']=len([n for n in dir(operator) if n.startswith('__') and n.endswith('__') and n not in ('__doc__','__name__','__file__','__loader__','__spec__','__package__','__builtins__','__all__')])
print(json.dumps(out,indent=1))
