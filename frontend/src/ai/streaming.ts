/**
 * Utility function to handle API streaming (chunked transfer encoding) responses.
 * Invokes callbacks on each parsed string chunk.
 */
export async function consumeStream(
  response: Response,
  onChunk: (text: string) => void,
  onComplete?: () => void
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Response body reader is not available.");
  }

  const decoder = new TextDecoder("utf-8");
  let done = false;

  try {
    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        const chunkText = decoder.decode(value, { stream: !done });
        onChunk(chunkText);
      }
    }
    if (onComplete) {
      onComplete();
    }
  } catch (error) {
    console.error("Stream consumption error:", error);
    throw error;
  } finally {
    reader.releaseLock();
  }
}
