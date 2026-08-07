import json, math, decimal, fractions, sys
r={}
def t(label, fn):
    try:
        v=fn()
        r[label]={'outcome':'value','repr':repr(v),'type':type(v).__name__}
    except Exception as e:
        r[label]={'outcome':'exception','exc':type(e).__name__,'msg':str(e)}
t('int_1_div_0', lambda: 1/0)
t('float_1.0_div_0.0', lambda: 1.0/0.0)
t('int_floordiv_0', lambda: 1//0)
t('int_mod_0', lambda: 1%0)
t('math_sqrt_neg1', lambda: math.sqrt(-1))
t('cmath_sqrt_neg1', lambda: __import__('cmath').sqrt(-1))
t('pow_neg1_half', lambda: (-1)**0.5)
t('math_log_0', lambda: math.log(0))
t('math_log_neg1', lambda: math.log(-1))
t('float_inf_minus_inf', lambda: float('inf')-float('inf'))
t('zero_times_inf', lambda: 0.0*float('inf'))
t('nan_eq_nan', lambda: float('nan')==float('nan'))
t('0_pow_0', lambda: 0**0)
t('0.0_pow_0.0', lambda: 0.0**0.0)
t('decimal_1_div_0', lambda: decimal.Decimal(1)/decimal.Decimal(0))
t('fraction_1_div_0', lambda: fractions.Fraction(1,0))
t('int_overflow_2**10000_bits', lambda: (2**10000).bit_length())
t('float_overflow_1e308*10', lambda: 1e308*10)
t('int_to_float_overflow', lambda: float(2**10000))
t('str_plus_int', lambda: "a"+1)
t('list_index_oob', lambda: [1,2,3][9])
t('undefined_name', lambda: eval("nonexistent_name_xyz"))
t('none_attr', lambda: None.foo)
t('bool_is_int_subclass', lambda: issubclass(bool,int))
t('true_plus_true', lambda: True+True)
t('float_eq_int', lambda: 1.0==1)
t('float_0.1_plus_0.2', lambda: 0.1+0.2)
t('int_div_gives_float', lambda: type(4/2).__name__)
r['float_repr_roundtrip']= (0.1+0.2==0.3)
r['sys_float_info']={'mant_dig':sys.float_info.mant_dig,'max':sys.float_info.max}
print(json.dumps(r,indent=1))
