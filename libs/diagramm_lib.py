import numpy as np
import os
from enum import Enum
import pandas as pd
from copy import deepcopy
import json
from libs.odbc_access_lib import expODBC


class ExperimentType(str, Enum):
    COMPRESSION = 'c'
    TENSION = 't'


def MLR(eA: float) -> float:
    return 1-0.6058*eA**2+0.6317*eA**3-0.2107*eA**4


class Diagramm:
    def __init__(self, t=[], e=[], s=[], de=[], etype=ExperimentType.COMPRESSION,
                 T=20):
        self._t: np.ndarray = np.array(t, dtype=np.float32)
        self._e: np.ndarray = np.array(e, dtype=np.float32)
        self._s: np.ndarray = np.array(s, dtype=np.float32)
        self._de: np.ndarray = np.array(de, dtype=np.float32)
        self.etype = etype
        self.ds: float = 0
        self.T = T
        self.set_initial_values()
    
    def set_initial_values(self):
        self._ep1: float = -1
        self._ep2: float = -1
        self._eN: float = -1
        self._ep1_idx: int = -1
        self._ep2_idx: int = -1
        self._eN_idx: int = -1
        self._E_multiplier: float = 1.0
        self._delta_e: float = 0.0
        self._MLR_correction: bool = False
        self._d0: float = -1
        self._d: float = -1
        self.exp_code = ''

    def load_from_txt(self, filepath: str):
        if not os.path.exists(filepath):
            print(f'Не найден файл {filepath}')
            return
        self.set_initial_values()
        self._t, self._e, self._s, self._de = np.genfromtxt(
            filepath,
            skip_header=1,
            unpack=True,
            usecols=[0, 1, 2, 3],
            )

    def load_from_xls(self, xls_path: str, sheet_name: str):
        if not os.path.exists(xls_path):
            print(f'Не найден файл {xls_path}')
            return
        self.set_initial_values()
        data = pd.read_excel(
            xls_path,
            sheet_name=sheet_name,
            usecols=[0, 5, 6, 7],
            names=['t', 'e', 's', 'de']
        )
        common_data = pd.read_excel(
            xls_path,
            sheet_name=0,
            usecols=[0, 4],
            names=['code', 'T'],
            index_col=0
        )
        self._t = data.t.to_numpy()
        self._e = data.e.to_numpy()
        self._s = data.s.to_numpy()
        self._de = data.de.to_numpy()
        self.exp_code = sheet_name
        self.etype = sheet_name[0]
        self.T = int(common_data.loc[sheet_name].T.values[0])
        
    def load_from_db(self, db: expODBC, exp_code: str):
        if db is None:
            print(f'База данных не подключена')
            return
        self.set_initial_values()
        diag = db.getDiagram(exp_code)
        if not diag:
            return
        self._t = np.array(diag['t'])
        self._e = np.array(diag['et'])
        self._s = np.array(diag['st'])
        self._de = np.array(diag['det'])
        self.exp_code = exp_code
        self.etype = exp_code[0]
        exp_data = db.getExperimentData(exp_code)
        self.T = exp_data.T
        self._d0 = exp_data.d0
        self._d = exp_data.d
        self._MLR_correction = False
    
    @property
    def ep1(self) -> float:
        return self._ep1

    @property
    def ep2(self) -> float:
        return self._ep2

    @property
    def eN(self) -> float:
        return self._eN

    @property
    def ep1_idx(self) -> int:
        return self._ep1_idx
    
    @property
    def ep2_idx(self) -> int:
        return self._ep2_idx

    @property
    def eN_idx(self) -> int:
        return self._eN_idx
    
    @ep1.setter
    def ep1(self, value: float):
        self._ep1 = value
        for i, e in enumerate(self._e):
            if e >= self._ep1:
                break
        else:
            self._ep1_idx = -1
            return
        self._ep1_idx = i

    @ep2.setter
    def ep2(self, value: float):
        self._ep2 = value
        for i, e in enumerate(self._e):
            if e >= self._ep2:
                break
        else:
            self._ep2_idx = -1
            return
        self._ep2_idx = i

    @eN.setter
    def eN(self, value: float):
        self._eN = value
        for i, e in enumerate(self._e):
            if e >= self._eN:
                break
        else:
            self._eN_idx = -1
            return
        self._eN_idx = i
    
    @property
    def e(self) -> np.ndarray:
        res = np.zeros(len(self._e))
        for i in range(len(self._e)):
            if i <= self._ep1_idx:
                res[i] = self._e[i]*self._E_multiplier
            else:
                res[i] = self._e[i]-self._e[self._ep1_idx]*(1-self._E_multiplier)
        return res + self._delta_e
    
    @property
    def s(self) -> np.ndarray:
        return self._s + self.ds
    
    @property
    def ep_eng(self) -> np.ndarray:
        if self.ep1_idx == -1:
            return np.array([])
        if self.ep2_idx == -1:
            return np.array([])
        rez = np.array(self._e[self.ep1_idx:self.ep2_idx])
        rez -= rez[0]
        return rez

    @property
    def sp_eng(self) -> np.ndarray:
        if self.ep1_idx == -1:
            return np.array([])
        if self.ep2_idx == -1:
            return np.array([])
        return self.s[self.ep1_idx:self.ep2_idx]

    @property
    def dep_eng(self) -> np.ndarray:
        if self.ep1_idx == -1:
            return np.array([])
        if self.ep2_idx == -1:
            return np.array([])
        return self.s[self.ep1_idx:self.ep2_idx]

    @property
    def ep_true(self) -> np.ndarray:
        sign = -1 if self.etype == ExperimentType.COMPRESSION else 1
        ep_tr = sign*np.log(1+sign*self.ep_eng) 
        if self._MLR_correction and (N:=(self.eN_idx-self.ep1_idx))>0:
            ep_tr = ep_tr[:N]
            if self._d0!=0 and self._d!=0:
                ep_1 = np.log(self._d0**2/self._d**2)
                ep_tr = np.array(ep_tr.tolist()+[ep_1])
        return ep_tr

    @property
    def sp_true(self) -> np.ndarray:
        sign = -1 if self.etype == ExperimentType.COMPRESSION else 1
        sp_tr = self.sp_eng*(1+sign*self.ep_eng)
        if self._MLR_correction and (N:=(self.eN_idx-self.ep1_idx))>0:
            sp_tr = sp_tr[:N]
            if self._d0!=0 and self._d!=0:
                ep = np.log(self._d0**2/self._d**2)
                sp_1 = self._d0**2/self._d**2*self.s[self.ep2_idx]*MLR(ep-(self.e[self.eN_idx]-self.e[self.ep1_idx]))
                sp_tr = np.array(sp_tr.tolist()+[sp_1])
        return sp_tr
    
    @property
    def dep_true(self) -> np.ndarray:
        sign = -1 if self.etype == ExperimentType.COMPRESSION else 1
        dep_tr = self.dep_eng/(1+sign*self.ep_eng)
        if self._MLR_correction and (N:=(self.eN_idx-self.ep1_idx))>0:
            dep_tr = dep_tr[:N]
        return dep_tr
    
    @property
    def as_dict(self) -> dict:
        rez = deepcopy(self.__dict__)
        rez['_t'] = list(self._t)
        rez['_e'] = list(self._e)
        rez['_s'] = list(self._s)
        rez['_de'] = list(self._de)
        return rez

    def load_from_json(self, json_path: str):
        if not os.path.exists(json_path):
            return
        data = json.load(open(json_path, 'r'))
        self._t = np.array(data['_t'])
        self._e = np.array(data['_e'])
        self._s = np.array(data['_s'])
        self._de = np.array(data['_de'])
        self._E_multiplier = data['_E_multiplier']
        self._delta_e = data['_delta_e']
        self._ep1 = data['_ep1']
        self._ep2 = data['_ep2']
        self._eN = data['_eN']
        self._ep1_idx = data['_ep1_idx']
        self._ep2_idx = data['_ep2_idx']
        self._eN_idx = data['_eN_idx']
        self.exp_code = data['exp_code']
        self.ds = data.get('ds', 0)
        self.T = data.get('T', 20)
        self._d0 = data.get('_d0', 0)
        self._d = data.get('_d', 0)
        self._MLR_correction = data['_MLR_correction']
        self.etype = self.exp_code[0]

    @property
    def mean_de_eng(self) -> float:
        return self.dep_eng.mean()

    @property
    def mean_de_true(self) -> float:
        return self.dep_true.mean()
        
    
if __name__=='__main__':
    common_data = pd.read_excel(
        r'E:\Work\NIIM\projects\correct_module\example\c714.xls',
        sheet_name=0,
        usecols=[0, 4],
        names=['code', 'T'],
        index_col=0
    )
    print(common_data.loc['c714-01'].T.values[0])