Ciao Andre,

Nel file `dizionario_estratto_finale.csv` ci sono le colonne "link", "definizione" e "esempio".
Se un lemma ha più esempi o definizioni è distribuito su più righe. Ti consiglio di aggiungere la colonna "lemma" dal file originale facendo un merge con "link" come id univoco.
Ti consiglio anche di pulire la colonna esempio dal nome degli autori e delle pagine con delle regex che cancellino tutto quello che c'è tra parentesi quadra chiusa `]` e i due punti `:`.

Se vuoi importare i file nel tuo codice basta copiare il permalink (o non mi ricordo quale link) nella pagina del file e inserirla in questa sintassi:

```
import pandas as pd

# 1. Inserisci il link alla versione "Raw" del file
url_csv = "https://raw.githubusercontent.com/simo-mazzoli/lemma/main/lemmi.csv"

df = pd.read_csv(url_csv)

print(df.head())
```
