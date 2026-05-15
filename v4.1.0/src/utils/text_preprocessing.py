import pandas as pd
import re 

def preprocess_wordcloud(dataframe: pd.DataFrame) -> str:

    texto = ' '.join(dataframe['title'].fillna("").astype(str) + ' ' + dataframe['summary'].fillna("").astype(str))
    texto = texto.lower()
    texto = re.sub(r"http\S+|www\S+|[^a-zA-ZáéíóúÁÉÍÓúñÑ\s]", "", texto)
    texto = ' '.join([w for w in texto.split() if len(w) > 3])
    
    return texto

def preprocess_resumen(df: pd.DataFrame) -> str:
    noticias_texto = ""
    for idx, row in df.iterrows():
        # Usar pd.notna para manejar posibles None o NaN de forma segura
        titulo = str(row['title']) if pd.notna(row['title']) else "[Sin Título]"
        resumen_noticia = str(row['summary']) if pd.notna(row['summary']) else "[Sin Resumen]"
        noticias_texto += f"\n{idx+1}. Título: {titulo}\n   Resumen: {resumen_noticia}\n"

    return noticias_texto