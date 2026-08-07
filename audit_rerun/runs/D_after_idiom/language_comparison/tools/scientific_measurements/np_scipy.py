import json, warnings, sys
warnings.filterwarnings('ignore')
import numpy as np
out={'numpy_version':np.__version__,'python':sys.version.split()[0]}
ufs=sorted(n for n in dir(np) if isinstance(getattr(np,n),np.ufunc))
out['numpy_ufunc_count']=len(ufs); out['numpy_ufuncs']=ufs
pub=[n for n in dir(np) if not n.startswith('_')]
out['numpy_toplevel_public_names']=len(pub)
dts=sorted({np.dtype(t).name for t in np.sctypeDict.values()}) if hasattr(np,'sctypeDict') else None
out['numpy_distinct_dtype_names_count']=len(dts) if dts else None
out['numpy_distinct_dtype_names']=dts
try:
    out['numpy_scalar_type_count']=len(set(np.sctypeDict.values()))
except Exception as e: out['numpy_scalar_type_count']=str(e)
# error policy
def t(l,f):
    try:
        with np.errstate(all='warn'):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                v=f()
                out[l]={'outcome':'value','repr':repr(v),'type':type(v).__name__,
                        'warnings':[str(x.message) for x in w]}
    except Exception as e:
        out[l]={'outcome':'exception','exc':type(e).__name__,'msg':str(e)[:200]}
t('np.float64(1)/np.float64(0)', lambda: np.float64(1)/np.float64(0))
t('np.array([1.0])/np.array([0.0])', lambda: np.array([1.0])/np.array([0.0]))
t('np.array([1])//np.array([0])  int', lambda: np.array([1])//np.array([0]))
t('np.array([0.0])/np.array([0.0])', lambda: np.array([0.0])/np.array([0.0]))
t('np.sqrt(-1.0)', lambda: np.sqrt(-1.0))
t('np.sqrt(np.complex128(-1))', lambda: np.sqrt(np.complex128(-1)))
t('np.log(0.0)', lambda: np.log(0.0))
t('np.log(-1.0)', lambda: np.log(-1.0))
t('np.array([1,2])+np.array([1,2,3])  shape mismatch', lambda: np.array([1,2])+np.array([1,2,3]))
t('np.linalg.inv(singular)', lambda: np.linalg.inv(np.array([[1.,2.],[2.,4.]])))
t('np.linalg.solve(singular,b)', lambda: np.linalg.solve(np.array([[1.,2.],[2.,4.]]), np.array([1.,2.])))
t('np.int8(127)+np.int8(1)  overflow', lambda: np.int8(127)+np.int8(1))
t('np.array([127],dtype=np.int8)+1', lambda: np.array([127],dtype=np.int8)+np.array([1],dtype=np.int8))
t('np.nan == np.nan', lambda: np.nan==np.nan)
t('broadcast (3,1)+(1,4)', lambda: (np.ones((3,1))+np.ones((1,4))).shape)
t('matmul shape mismatch (2,3)@(2,3)', lambda: np.ones((2,3))@np.ones((2,3)))
t('reshape wrong size', lambda: np.arange(6).reshape(4,2))
out['default_errstate']=dict(np.geterr())
# einsum / shape typing: is shape part of the static type? No -- demonstrate ndarray dtype has no shape
a=np.ones((3,4))
out['ndarray_dtype_has_shape']= 'shape' in dir(a.dtype)
out['ndarray_type_name']=type(a).__name__
out['ndarray_type_is_same_for_all_shapes']= (type(np.ones((3,4))) is type(np.ones((7,))))
# scipy
try:
    import scipy, scipy.stats as sst, scipy.special as ssp
    out['scipy_version']=scipy.__version__
    cont=[n for n in dir(sst) if isinstance(getattr(sst,n), sst.rv_continuous)]
    disc=[n for n in dir(sst) if isinstance(getattr(sst,n), sst.rv_discrete)]
    out['scipy_stats_continuous_dist_count']=len(cont)
    out['scipy_stats_discrete_dist_count']=len(disc)
    out['scipy_stats_total_named_dists']=len(cont)+len(disc)
    out['scipy_special_public_callables']=len([n for n in dir(ssp) if not n.startswith('_') and callable(getattr(ssp,n))])
    out['scipy_special_ufunc_count']=len([n for n in dir(ssp) if isinstance(getattr(ssp,n),np.ufunc)])
    import scipy.linalg
    out['scipy_submodules']=sorted([m for m in ['cluster','constants','datasets','fft','fftpack','integrate','interpolate','io','linalg','ndimage','odr','optimize','signal','sparse','spatial','special','stats']])
except Exception as e:
    out['scipy_error']=str(e)
print(json.dumps(out,indent=1,default=str))
