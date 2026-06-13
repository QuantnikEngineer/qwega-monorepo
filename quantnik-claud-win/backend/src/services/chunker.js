// Recursive character splitter — LangChain-flavoured but tiny. Splits on the
// largest semantic boundary that fits, falling through ever-finer separators
// until each chunk is under the target token count. ~4 chars/token heuristic
// keeps this dependency-free (no tokeniser).

const DEFAULT_TARGET_TOKENS  = 500;
const DEFAULT_OVERLAP_TOKENS = 50;
const SEPARATORS = ['\n\n', '\n', '. ', ', ', ' ', ''];
const APPROX_CHARS_PER_TOKEN = 4;

function approxTokens(s) {
  return Math.ceil(s.length / APPROX_CHARS_PER_TOKEN);
}

function splitOn(text, sep) {
  if (sep === '') return text.split('');
  const parts = text.split(sep);
  // Re-attach the separator to every part except the last so concatenation
  // round-trips the original text faithfully.
  return parts.map((p, i) => (i < parts.length - 1 ? p + sep : p));
}

function mergePieces(pieces, targetChars, overlapChars) {
  const chunks = [];
  let current = '';
  let currentStart = 0;
  let cursor = 0;

  function flush(endCursor) {
    if (!current.length) return;
    chunks.push({ content: current, start: currentStart, end: endCursor });
    if (overlapChars > 0 && current.length > overlapChars) {
      // Slide the window: keep the tail as overlap for the next chunk.
      const tail = current.slice(-overlapChars);
      current = tail;
      currentStart = endCursor - tail.length;
    } else {
      current = '';
      currentStart = endCursor;
    }
  }

  for (const piece of pieces) {
    if (current.length + piece.length > targetChars && current.length > 0) {
      flush(cursor);
    }
    current += piece;
    cursor += piece.length;
    while (current.length > targetChars) {
      // The piece alone is bigger than target — slice hard.
      const slice = current.slice(0, targetChars);
      chunks.push({ content: slice, start: currentStart, end: currentStart + slice.length });
      current = current.slice(targetChars - overlapChars);
      currentStart += targetChars - overlapChars;
    }
  }
  flush(cursor);
  return chunks;
}

/**
 * Split `text` into chunks of approximately `targetTokens` tokens each,
 * preferring breaks at paragraph > line > sentence > word boundaries.
 * Returns [{ content, start, end, tokens }].
 */
export function chunk(text, { targetTokens = DEFAULT_TARGET_TOKENS, overlapTokens = DEFAULT_OVERLAP_TOKENS } = {}) {
  if (!text || !text.trim()) return [];
  const targetChars  = targetTokens  * APPROX_CHARS_PER_TOKEN;
  const overlapChars = overlapTokens * APPROX_CHARS_PER_TOKEN;

  // Walk separators from largest to smallest. First one that splits the text
  // into pieces ≤ targetChars wins. If we exhaust all separators and a piece
  // is still too large, mergePieces hard-slices.
  let pieces = [text];
  for (const sep of SEPARATORS) {
    if (pieces.every((p) => p.length <= targetChars)) break;
    pieces = pieces.flatMap((p) => (p.length > targetChars ? splitOn(p, sep) : [p]));
  }

  const merged = mergePieces(pieces, targetChars, overlapChars);
  return merged.map((c) => ({ ...c, tokens: approxTokens(c.content) }));
}

export { approxTokens };
