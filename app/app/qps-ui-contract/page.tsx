import { QPS_UI_TOKENS, QPS_UI_VERSION } from '@/lib/qps-ui-tokens';

export default function QpsUiContractPage() {
  return (
    <main className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">QPS UI Contract v{QPS_UI_VERSION}</h1>
        <p className="text-sm text-muted-foreground">
          Read-only operational proof that the Next surface consumes the same governed token vocabulary as the Jekyll evidence atlas.
        </p>
      </header>
      <section>
        <h2 className="text-xl font-medium">States</h2>
        <ul className="mt-2 space-y-1">
          {Object.entries(QPS_UI_TOKENS.states).map(([name, token]) => (
            <li key={name}><code>{name}</code> → <code>{token.class}</code> ({token.symbol})</li>
          ))}
        </ul>
      </section>
      <section>
        <h2 className="text-xl font-medium">Flows</h2>
        <ul className="mt-2 space-y-1">
          {Object.entries(QPS_UI_TOKENS.flows).map(([name, token]) => (
            <li key={name}><code>{name}</code> → {token.line} / {token.arrow}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
