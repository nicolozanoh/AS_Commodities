from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

def crear_nube(texto, fecha, path):
    path = Path(path)
    stopwords = set(STOPWORDS)
    palabras_excluir = {
        'price', 'prices', 'month', 'year', 'week', 'oil', 'first', 'crude', 'coffee', 'gold',
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
        'monday', 'friday', 'tuesday', 'wednesday', 'thursday', 'saturday', 'sunday',
        'said', 'reports', 'report', 'according', 'new', 'news', 'will', 'one', 'two', 'three', 'also',
        'weekly', 'today'
    }
    stopwords.update(palabras_excluir)

    try:
        nube = WordCloud(
            width=900, height=700, background_color='white',
            colormap='inferno', stopwords=stopwords
        ).generate(texto)

        fig = plt.figure(figsize=(12, 6))
        plt.imshow(nube, interpolation='bilinear')
        plt.axis('off')
        plt.title('Nube de Palabras', fontsize=16, pad=20)

        try:
            nube_dir = path / "resumen" / "nube"
            nube_dir.mkdir(parents=True, exist_ok=True)
            out = nube_dir / f"nube - {fecha.strftime('%d%b%Y').lower()}.png"
            fig.savefig(out, dpi=300, bbox_inches='tight')
            print(f"[NubePalabras] Imagen guardada en {out}")
        except Exception as e_save:
            print(f"[NubePalabras] Error al guardar la imagen: {e_save}")

        plt.close(fig)

    except Exception as e:
        print(f"[NubePalabras] Error al generar la nube de palabras: {e}")
