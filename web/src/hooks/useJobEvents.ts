import { useEffect } from "react";

import type { JobEvent } from "../types";

interface UseJobEventsOptions {
  jobId: string | null;
  onEvent: (event: JobEvent) => void;
  onEnd?: () => void;
}

export function useJobEvents({ jobId, onEvent, onEnd }: UseJobEventsOptions) {
  useEffect(() => {
    if (!jobId) {
      return;
    }

    const source = new EventSource(`/api/jobs/${jobId}/events`);

    source.addEventListener("job_event", (rawEvent) => {
      try {
        const message = JSON.parse((rawEvent as MessageEvent).data) as JobEvent;
        onEvent(message);
      } catch (error) {
        console.error("Failed to parse SSE event", error);
      }
    });

    source.addEventListener("end", () => {
      onEnd?.();
      source.close();
    });

    source.onerror = () => {
      source.close();
    };

    return () => {
      source.close();
    };
  }, [jobId, onEvent, onEnd]);
}
