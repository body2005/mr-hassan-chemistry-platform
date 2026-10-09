import { useEffect, useState } from "react";
import { authService } from "../services/lmsService";

export function usePasswordResetAvailability(): boolean | null {
  const [available, setAvailable] = useState<boolean | null>(null);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const features = await authService.getFeatures();
        if (active) setAvailable(features.password_reset_enabled === true);
      } catch {
        // Do not offer email recovery when the server cannot confirm it.
        if (active) setAvailable(false);
      }
    }
    void load();
    return () => { active = false; };
  }, []);
  return available;
}
