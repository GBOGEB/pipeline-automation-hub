// Minimal Node declarations for tools/check_model.mts, so the type-check needs only `typescript`
// (no @types/node download). Extend if the tool grows.
declare module "node:module" {
  export function createRequire(url: string): (id: string) => unknown;
}
declare const process: { exit(code?: number): never; argv: string[]; env: Record<string, string | undefined> };
declare const console: { log(...a: unknown[]): void; error(...a: unknown[]): void };
interface ImportMeta { url: string }
