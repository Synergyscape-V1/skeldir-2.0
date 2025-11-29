#!/usr/bin/env python3
"""
Validate that generated Pydantic models can be imported and used.
Tests model structure integrity for B0.1 baseline.
"""

import sys
from pathlib import Path

def validate_model_imports():
    """Validate all critical models can be imported."""
    errors = []

    # Critical models that must be importable
    critical_models = {
        'attribution': ['RealtimeRevenueResponse', 'RealtimeRevenueCounter', 'ChannelAttribution'],
        'auth': ['LoginRequest', 'LoginResponse', 'RefreshRequest', 'RefreshResponse'],
        'reconciliation': ['ReconciliationStatusResponse'],
        'export': ['ExportRevenueResponse'],
        'webhooks_shopify': ['ShopifyOrderCreateRequest', 'WebhookAcknowledgement'],
        'webhooks_stripe': ['StripeChargeSucceededRequest', 'StripeChargeRefundedRequest'],
        'webhooks_woocommerce': ['WooCommerceOrderCompletedRequest'],
        'webhooks_paypal': ['PayPalSaleCompletedRequest'],
    }

    for module_name, models in critical_models.items():
        try:
            module = __import__(f'backend.app.schemas.{module_name}', fromlist=models)
            for model in models:
                if not hasattr(module, model):
                    errors.append(f"Model {model} not found in backend.app.schemas.{module_name}")
                else:
                    print(f"✓ backend.app.schemas.{module_name}.{model}")
        except ImportError as e:
            errors.append(f"Failed to import backend.app.schemas.{module_name}: {e}")

    if errors:
        print("\nValidation Errors:")
        for error in errors:
            print(f"  ✗ {error}")
        return False

    print("\n✓ All critical models validated successfully")
    return True

def main():
    """Main validation entry point."""
    print("Validating Pydantic model structures...")

    # Add project root to Python path
    repo_root = Path(__file__).parent.parent
    sys.path.insert(0, str(repo_root))

    success = validate_model_imports()

    if not success:
        sys.exit(1)

    print("Model validation complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
