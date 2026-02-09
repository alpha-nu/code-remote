/**
 * Hook that reveals text progressively to create a typewriter effect.
 *
 * Takes the full "target" text (which may grow over time as streaming chunks
 * arrive) and returns a substring that grows character-by-character at a
 * configurable speed.
 *
 * When the target text grows (new chunk appended), the hook queues the new
 * characters and continues revealing from where it left off — no restart.
 */

import { useEffect, useRef, useState } from 'react';

interface UseTypewriterOptions {
  /** Characters to reveal per tick. Default: 2 */
  charsPerTick?: number;
  /** Milliseconds between ticks. Default: 12 */
  intervalMs?: number;
}

export function useTypewriter(
  targetText: string,
  options: UseTypewriterOptions = {},
): string {
  const { charsPerTick = 2, intervalMs = 12 } = options;

  const [revealedLength, setRevealedLength] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // When targetText grows, start/continue the reveal interval
  useEffect(() => {
    // Nothing to reveal — stay at 0
    if (!targetText) {
      setRevealedLength(0);
      return;
    }

    // Already fully revealed — just snap
    if (revealedLength >= targetText.length) {
      return;
    }

    // Start ticking if not already
    if (intervalRef.current === null) {
      intervalRef.current = setInterval(() => {
        setRevealedLength((prev) => {
          // Access current targetText length via closure
          // — the interval captures the ref, not the stale variable
          return prev + charsPerTick;
        });
      }, intervalMs);
    }

    return () => {
      // Cleanup only on unmount — we don't want to stop the interval
      // just because targetText updated
    };
    // We deliberately depend on targetText.length (not the whole string)
    // to restart when new chunks arrive.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetText.length, charsPerTick, intervalMs]);

  // Stop the interval once we've caught up
  useEffect(() => {
    if (revealedLength >= targetText.length && intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, [revealedLength, targetText.length]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);

  // Clamp to targetText length (safety)
  const clamped = Math.min(revealedLength, targetText.length);
  return targetText.slice(0, clamped);
}
