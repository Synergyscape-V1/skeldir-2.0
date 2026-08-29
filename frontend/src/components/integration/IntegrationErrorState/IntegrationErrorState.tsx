import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';

export interface IntegrationErrorStateProps {
  message: string;
  id?: string;
}

export function IntegrationErrorState({ message, id }: IntegrationErrorStateProps) {
  return (
    <div id={id} data-integration-error role="alert" aria-live="assertive">
      <ErrorBanner message={message} />
    </div>
  );
}
