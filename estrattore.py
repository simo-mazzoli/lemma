import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import io
import sys
import os

# --- CONFIGURAZIONE ---
# Link aggiornato al tuo file CSV
URL_CSV_GITHUB = "https://raw.githubusercontent.com/simo-mazzoli/lemma/main/lemmi.csv"
COLONNA_LINK = "link"  # Assicurati che l'intestazione nel CSV sia esattamente "link" (minuscolo)
NOME_FILE_OUTPUT = "dizionario_tlio_completo.csv"

# Imposta a True se vuoi vedere le prime righe lette per ogni sito (utile per capire errori)
DEBUG_MODE = False 

def pulisci_testo(testo):
    """Rimuove spazi doppi, tabulazioni e spazi invisibili."""
    return re.sub(r'\s+', ' ', testo).strip()

def is_definizione_valida(riga):
    """
    Distingue una vera definizione da un numero di pagina o un anno.
    Esempio valido: "1 Tornare..."
    Esempio invalido: "143.30 pag. 20..." (Pagina)
    """
    match = re.match(r"^(\d+(?:\.\d+)*)\.?", riga)
    if not match:
        return False
    
    numero_str = match.group(1) 
    
    try:
        parte_intera = int(numero_str.split('.')[0])
        
        # 1. Nessun lemma ha più di 50 definizioni. Se > 50 è una pagina/anno.
        if parte_intera > 50: 
            return False 
        
        # 2. Filtra anni storici (es. 1250, 1300) se appaiono a inizio riga
        if 1000 < parte_intera < 2100:
            return False
            
    except ValueError:
        pass 

    # 3. Controlla parole chiave di citazione subito dopo il numero
    testo_dopo = riga[len(numero_str):].strip().lower()
    if testo_dopo.startswith('.'): testo_dopo = testo_dopo[1:].strip()
        
    indicatori_citazione = ["pag", "cap", "vol", "ed.", "fol", "c.", "l.", "a.", "cfr"]
    for ind in indicatori_citazione:
        if testo_dopo.startswith(ind):
            return False

    return True

def estrai_dati_da_tlio(url, debug=False):
    dati_estratti = []
    
    try:
        # Header generico per simulare un browser
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.encoding = response.apparent_encoding 
        
        if response.status_code != 200:
            print(f" -> Errore HTTP: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- PRE-PROCESSING DEL TESTO ---
        # 1. Sostituisce i <br> con "a capo" reali
        for br in soup.find_all("br"):
            br.replace_with("\n")
        
        # 2. Estrae il testo mantenendo la struttura
        testo_completo = soup.get_text(separator="\n")
        
        # 3. Rimuove lo spazio "non-breaking" (\xa0) che spesso rompe le regex
        testo_completo = testo_completo.replace(u'\xa0', ' ')
        
        # Divide in righe pulite
        righe = [r.strip() for r in testo_completo.split("\n") if r.strip()]

        if debug:
            print(f"\n[DEBUG] Anteprima contenuto letto da {url}:")
            for x in righe[:5]: print(f"   | {x}")
            print("-" * 40)

        # --- LOGICA DI ESTRAZIONE A BUFFER ---
        definizione_attuale = "N/A"
        buffer_tipo = None  # 'DEF' o 'ESEMPIO'
        buffer_testo = []
        
        regex_def_candidate = re.compile(r"^\d+(\.\d+)*\.?") # Es: 1, 1.1, 2.
        regex_ex_start = re.compile(r"^\[\d+\]")             # Es: [1], [12]

        def salva_buffer():
            """Salva il contenuto accumulato finora nel buffer."""
            nonlocal definizione_attuale
            testo_unito = pulisci_testo(" ".join(buffer_testo))
            
            if not testo_unito: return

            if buffer_tipo == 'DEF':
                definizione_attuale = testo_unito
            elif buffer_tipo == 'ESEMPIO':
                dati_estratti.append({
                    "link_originale": url,
                    "definizione": definizione_attuale,
                    "esempio": testo_unito
                })

        for riga in righe:
            is_ex = regex_ex_start.match(riga)
            is_def = False
            
            # Verifica se è una definizione valida (e non un numero di pagina)
            if regex_def_candidate.match(riga) and not is_ex:
                if is_definizione_valida(riga):
                    is_def = True

            # Gestione cambio stato
            if is_def:
                salva_buffer() # Chiude il blocco precedente
                buffer_tipo = 'DEF'
                buffer_testo = [riga]
            
            elif is_ex:
                salva_buffer() # Chiude il blocco precedente
                buffer_tipo = 'ESEMPIO'
                buffer_testo = [riga]
            
            else:
                # Continuazione del testo precedente (riga spezzata)
                if buffer_tipo is not None:
                    buffer_testo.append(riga)

        # Salvataggio finale ultimo blocco
        salva_buffer()

    except Exception as e:
        print(f" -> Eccezione durante l'elaborazione: {e}")

    return dati_estratti

def main():
    print("--- Inizio Processo ---")
    
    # 1. CARICAMENTO CSV
    print(f"Lettura CSV da: {URL_CSV_GITHUB}")
    try:
        df_input = pd.read_csv(URL_CSV_GITHUB)
        
        # Controllo colonna
        if COLONNA_LINK not in df_input.columns:
            print(f"ERRORE: La colonna '{COLONNA_LINK}' non esiste nel CSV.")
            print(f"Colonne trovate: {list(df_input.columns)}")
            return
            
        # Pulizia link vuoti
        df_input = df_input.dropna(subset=[COLONNA_LINK])
        df_input = df_input[df_input[COLONNA_LINK].astype(str).str.strip() != ""]
        
    except Exception as e:
        print(f"ERRORE CRITICO nel caricamento del CSV: {e}")
        return

    totale_link = len(df_input)
    print(f"Link validi trovati: {totale_link}")
    tutte_le_righe = []

    # 2. ELABORAZIONE LINK
    for i, row in df_input.iterrows():
        url = row[COLONNA_LINK]
        percentuale = round(((i + 1) / totale_link) * 100, 1)
        
        print(f"[{i+1}/{totale_link} - {percentuale}%] Elaborazione: {url}")
        
        # Attiviamo il debug solo sul primo link per controllo
        risultati = estrai_dati_da_tlio(url, debug=(i==0 and DEBUG_MODE))
        tutte_le_righe.extend(risultati)

    # 3. SALVATAGGIO
    if tutte_le_righe:
        df_output = pd.DataFrame(tutte_le_righe)
        df_output.to_csv(NOME_FILE_OUTPUT, index=False, encoding='utf-8-sig')
        
        print("\n" + "="*40)
        print(f"COMPLETATO CON SUCCESSO!")
        print(f"Totale righe estratte: {len(df_output)}")
        print(f"File salvato come: {NOME_FILE_OUTPUT}")
        print("="*40)
        
        # Download automatico se su Colab
        try:
            from google.colab import files
            print("Avvio download automatico (Google Colab)...")
            files.download(NOME_FILE_OUTPUT)
        except ImportError:
            print(f"Il file si trova in: {os.path.abspath(NOME_FILE_OUTPUT)}")
    else:
        print("\nATTENZIONE: Nessun dato estratto. Verifica i link o la struttura delle pagine.")

if __name__ == "__main__":
    main()
