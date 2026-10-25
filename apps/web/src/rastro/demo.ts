export function rastroDemoEnabled(): boolean {
  return import.meta.env.VITE_RASTRO_DEMO !== "false";
}
