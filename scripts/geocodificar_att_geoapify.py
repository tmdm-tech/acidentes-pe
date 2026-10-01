#!/usr/bin/env python3
import os, re, json, time, argparse, unicodedata
from pathlib import Path
import requests
import pandas as pd

API = "https://api.geoapify.com/v1/geocode/search"

def norm(s):
    if pd.isna(s): return ""
    return re.sub(r"\s+"," ",str(s)).strip()

def pick_col(cols, candidates):
    m={unicodedata.normalize("NFKD",c).encode("ascii","ignore").decode().lower():c for c in cols}
    for x in candidates:
        k=unicodedata.normalize("NFKD",x).encode("ascii","ignore").decode().lower()
        if k in m:return m[k]
    return None

def geocode(address, city, key):
    q=", ".join(x for x in [norm(address),norm(city),"Pernambuco","Brasil"] if x)
    params={"text":q,"filter":"countrycode:br","bias":"countrycode:br","format":"json","limit":5,"apiKey":key}
    r=requests.get(API,params=params,timeout=30); r.raise_for_status()
    return q,r.json().get("results",[])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--output",default="outputs/ATT_geocodificado_geoapify.xlsx")
    args=ap.parse_args()
    key=os.environ.get("GEOAPIFY_API_KEY")
    if not key: raise SystemExit("GEOAPIFY_API_KEY não definido.")
    df=pd.read_excel(args.input)
    addr=pick_col(df.columns,["Endereco_Sinistro","Endereço_Sinistro","endereco_sinistro"])
    city=pick_col(df.columns,["Municipio_Notificacao","Município_Notificacao","municipio_notificacao"])
    lat=pick_col(df.columns,["Latitude","latitude"]) or "Latitude"
    lon=pick_col(df.columns,["Longitude","longitude"]) or "Longitude"
    if not addr or not city: raise SystemExit(f"Colunas de endereço/município não encontradas: {list(df.columns)}")
    for c in [lat,lon,"Geocodificacao_Consulta","Geocodificacao_Endereco","Geocodificacao_Cidade","Geocodificacao_Confianca","Geocodificacao_Tipo","Geocodificacao_Status"]:
        if c not in df.columns: df[c]=pd.NA
    cache={}
    for i,row in df.iterrows():
        a,c=norm(row[addr]),norm(row[city])
        if not a or a.upper() in {"IGNORADO","NÃO INFORMADO","NAO INFORMADO"}:
            df.at[i,"Geocodificacao_Status"]="SEM_ENDERECO_PRECISO"; continue
        ck=(a,c)
        try:
            if ck not in cache:
                cache[ck]=geocode(a,c,key); time.sleep(.22)
            q,res=cache[ck]
            df.at[i,"Geocodificacao_Consulta"]=q
            # Prefere resultado no município informado.
            cn=unicodedata.normalize("NFKD",c).encode("ascii","ignore").decode().lower()
            chosen=None
            for x in res:
                rc=norm(x.get("city") or x.get("municipality") or x.get("county"))
                rn=unicodedata.normalize("NFKD",rc).encode("ascii","ignore").decode().lower()
                if cn and (cn==rn or cn in rn or rn in cn): chosen=x; break
            if chosen is None and res: chosen=res[0]
            if not chosen:
                df.at[i,"Geocodificacao_Status"]="NAO_LOCALIZADO"; continue
            df.at[i,lat]=chosen.get("lat"); df.at[i,lon]=chosen.get("lon")
            df.at[i,"Geocodificacao_Endereco"]=chosen.get("formatted")
            df.at[i,"Geocodificacao_Cidade"]=chosen.get("city") or chosen.get("municipality") or chosen.get("county")
            df.at[i,"Geocodificacao_Confianca"]=(chosen.get("rank") or {}).get("confidence")
            df.at[i,"Geocodificacao_Tipo"]=chosen.get("result_type")
            df.at[i,"Geocodificacao_Status"]="GEOCODIFICADO"
        except Exception as e:
            df.at[i,"Geocodificacao_Status"]="ERRO: "+str(e)[:180]
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    df.to_excel(args.output,index=False)
    print(df["Geocodificacao_Status"].value_counts(dropna=False).to_string())
    print(args.output)
if __name__=="__main__": main()
