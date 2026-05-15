import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path


def graficar_indices(commodity):
    model_types = ["GPT", "LLM", "all_models"]

    excel_dir = commodity["output_path"] / "excel"
    excel_dir.mkdir(parents=True, exist_ok=True)

    grafs_dir = commodity["output_path"] / "grafs"
    grafs_dir.mkdir(parents=True, exist_ok=True)

    for mtype in model_types:
        df = pd.read_excel(excel_dir / f"sentimiento_diario_{mtype}.xlsx")
        df['fecha'] = pd.to_datetime(df['fecha'])
        df.set_index('fecha', inplace=True)

        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df[f'daily_sentiment_{mtype}'], label='Sentimiento Diario', linestyle=':', color='grey')
        plt.plot(df.index, df[f'MA_7_{mtype}'], label='MA 7 dias', color='red')
        plt.axhline(y=0, color='grey', linewidth=0.8)
        plt.title(f"Sentimiento Diario - {commodity['name'].capitalize()}")
        plt.xlabel("Fecha")
        plt.ylabel("Sentimiento Promedio")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(grafs_dir / f"indice_diario_{mtype}.png", dpi=300, bbox_inches='tight')
        plt.close()


def graficar_comparacion_modelos(commodity):
    excel_dir = commodity["output_path"] / "excel"
    df = pd.read_excel(excel_dir / "models_comparison.xlsx")
    df['fecha'] = pd.to_datetime(df['fecha'])
    df.set_index('fecha', inplace=True)

    columns = df.columns[df.columns.str.startswith('MA_7_')]

    grafs_dir = commodity["output_path"] / "grafs"
    grafs_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Graficas] Graficando comparacion de modelos  ({len(columns)} series)...")

    plt.figure(figsize=(10, 5))
    for col in columns:
        plt.plot(df.index, df[col], label=col)

    plt.axhline(y=0, color='black', linewidth=1)
    plt.title(f"Sentimiento Diario - {commodity['name'].capitalize()}")
    plt.xlabel("Fecha")
    plt.ylabel("Sentimiento Promedio")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.savefig(grafs_dir / "model_comparisson.png", dpi=300, bbox_inches='tight')
    plt.close()
