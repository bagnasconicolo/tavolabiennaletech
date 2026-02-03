/**
 * Endpoint per esportare campioni e stati da un foglio della tavola periodica.
 *
 * Colonna A: simbolo (una riga per ciascun elemento, da 1 a 118)
 * Colonne B–E: quattro campioni (celle colorate secondo la legenda)
 * Colonna G2:G?: legenda; ogni cella contiene un’etichetta e il colore di sfondo
 *
 * Restituisce un JSON con:
 *  - elements: lista di elementi (row, symbol, samples[ { value, state, color } ])
 *  - legend: mappa colore→etichetta
 *  - labelColors: mappa etichetta→colore
 * Pubblica questo progetto come Web App (esegui come te, accesso pubblico).
 * Facoltativamente puoi passare ?id=<spreadsheetId> per usare altri fogli.
 */
function doGet(e) {
  var defaultId = '1MsTlm8PyLOQwTxImSekqNZZi6DxgaEBSWBxkhqHw7T8';
  var sheetId = (e && e.parameter && e.parameter.id) ? e.parameter.id : defaultId;
  var ss;
  try {
    ss = SpreadsheetApp.openById(sheetId);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      error: 'openById failed',
      detail: String(err)
    })).setMimeType(ContentService.MimeType.JSON);
  }
  var sh = ss.getSheets()[0];
  // leggi le prime cinque colonne per tutte le righe utili
  var maxRows = sh.getMaxRows();
  var vals = sh.getRange(1, 1, maxRows, 5).getValues();
  var bgs  = sh.getRange(1, 1, maxRows, 5).getBackgrounds();
  // legenda G2:G?: etichette e colori (dinamico fino all'ultima riga del foglio)
  var lastRow = Math.max(sh.getLastRow(), 2);
  var legRange = sh.getRange(2, 7, lastRow - 1, 1); // colonna G, da riga 2
  var legVals = legRange.getValues();
  var legBgs  = legRange.getBackgrounds();
  var legend = {};
  var labelColors = {};
  for (var i = 0; i < legVals.length; i++) {
    var label = String(legVals[i][0] || '').trim();
    var colour = String(legBgs[i][0] || '').trim();
    if (label) {
      legend[colour] = label;
      labelColors[label] = colour;
    }
  }
  var elements = [];
  for (var r = 0; r < vals.length; r++) {
    var sym = String(vals[r][0] || '').trim();
    if (!sym) {
      // salta eventuali righe vuote
      continue;
    }
    var samples = [];
    for (var c = 1; c <= 4; c++) {
      var v  = vals[r][c];
      var bg = String(bgs[r][c] || '').trim();
      var state = legend[bg] || '';
      samples.push({
        value: v === null ? '' : v,
        state: state,
        color: bg
      });
    }
    var symbolBg = String(bgs[r][0] || '').trim(); // colonna A

    elements.push({
      row: r + 1,
      symbol: sym,
      symbolColor: symbolBg, 
      samples: samples
    });
  }
  return ContentService.createTextOutput(JSON.stringify({
    elements: elements,
    legend: legend,
    labelColors: labelColors
  })).setMimeType(ContentService.MimeType.JSON);
}
