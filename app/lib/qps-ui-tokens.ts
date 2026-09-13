import qpsUiTokens from '../../mission-control/qps-triage-ultra/web/QPS_UI_TOKENS_v1.2.json';

export type QpsState = keyof typeof qpsUiTokens.states;
export type QpsFlow = keyof typeof qpsUiTokens.flows;

export const QPS_UI_TOKENS = qpsUiTokens;
export const QPS_UI_VERSION = qpsUiTokens.schema.replace('qps.ui.tokens.v', '');

export function qpsStateClass(state: QpsState): string {
  return qpsUiTokens.states[state].class;
}
