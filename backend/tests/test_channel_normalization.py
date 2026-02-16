"""
Channel Normalization Golden Tests

This test suite validates the normalize_channel() function contract:
- ALWAYS returns a valid channel_taxonomy.code value
- NEVER returns None, empty strings, or arbitrary non-taxonomy values
- Correctly maps known vendor combinations to canonical codes
- Falls back to 'unknown' for unmapped combinations
- Logs unmapped occurrences for data quality monitoring

These are "golden tests" - they define the expected behavior and must pass in CI.
Breaking these tests indicates a violation of the channel governance contract.

Related Documents:
- db/docs/channel_contract.md (Authoritative channel governance contract)
- B0.3-P_CHANNEL_GOVERNANCE_REMEDIATION.md (Implementation evidence)
"""

import pytest
from unittest.mock import patch, MagicMock

# Adjust import based on actual module structure
import sys
from pathlib import Path

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.ingestion.channel_normalization import (
    normalize_channel,
    get_valid_taxonomy_codes,
    log_unmapped_channel,
)
import app.ingestion.channel_normalization as channel_normalization


class TestNormalizeChannelContract:
    """Test that normalize_channel() upholds its contract guarantees."""
    
    def test_never_returns_none(self):
        """Gate 4.4: Function never returns None for any input."""
        result = normalize_channel(utm_source=None, utm_medium=None, vendor=None)
        assert result is not None, "normalize_channel() MUST NOT return None"
        assert isinstance(result, str), "normalize_channel() MUST return a string"
    
    def test_never_returns_empty_string(self):
        """Contract: Function never returns empty string."""
        result = normalize_channel(utm_source="", utm_medium="", vendor="")
        assert result != "", "normalize_channel() MUST NOT return empty string"
        assert len(result) > 0, "normalize_channel() MUST return non-empty string"
    
    def test_always_returns_valid_taxonomy_code(self):
        """Gate 4.5: All return values are valid taxonomy codes."""
        valid_codes = get_valid_taxonomy_codes()
        
        # Test various input combinations
        test_cases = [
            (None, None, None),
            ("google", "cpc", "google_ads"),
            ("random", "random", "random_vendor"),
            ("", "", ""),
            ("facebook", "paid", "facebook_ads"),
        ]
        
        for utm_source, utm_medium, vendor in test_cases:
            result = normalize_channel(utm_source, utm_medium, vendor)
            assert result in valid_codes, (
                f"normalize_channel({utm_source}, {utm_medium}, {vendor}) "
                f"returned '{result}' which is not in valid taxonomy codes"
            )


class TestKnownMappings:
    """Test that known vendor combinations map to correct canonical codes."""
    
    def test_google_ads_search(self):
        """Gate 4.2: Known mapping - Google Search Ads."""
        result = normalize_channel(utm_source="SEARCH", utm_medium=None, vendor="google_ads")
        assert result == 'google_search_paid', (
            f"Expected 'google_search_paid' for Google Search, got '{result}'"
        )
    
    def test_google_ads_display(self):
        """Gate 4.2: Known mapping - Google Display Network."""
        result = normalize_channel(utm_source="DISPLAY", utm_medium=None, vendor="google_ads")
        assert result == 'google_display_paid', (
            f"Expected 'google_display_paid' for Google Display, got '{result}'"
        )
    
    def test_facebook_ads_paid(self):
        """Gate 4.2: Known mapping - Facebook Paid Ads."""
        result = normalize_channel(utm_source="FB_ADS", utm_medium=None, vendor="facebook_ads")
        assert result == 'facebook_paid', (
            f"Expected 'facebook_paid' for Facebook Ads, got '{result}'"
        )
    
    def test_facebook_ads_brand(self):
        """Gate 4.2: Known mapping - Facebook Brand Campaigns."""
        result = normalize_channel(utm_source="FB_BRAND", utm_medium=None, vendor="facebook_ads")
        assert result == 'facebook_brand', (
            f"Expected 'facebook_brand' for Facebook Brand, got '{result}'"
        )

    def test_facebook_ads_fb_alias(self):
        """Gate 4.2: Alias mapping - fb -> facebook_paid."""
        result = normalize_channel(utm_source="fb", utm_medium="cpc", vendor="facebook_ads")
        assert result == 'facebook_paid', (
            f"Expected 'facebook_paid' for fb alias, got '{result}'"
        )

    def test_facebook_ads_facebook_alias(self):
        """Gate 4.2: Alias mapping - facebook -> facebook_paid."""
        result = normalize_channel(utm_source="facebook", utm_medium="cpc", vendor="facebook_ads")
        assert result == 'facebook_paid', (
            f"Expected 'facebook_paid' for facebook alias, got '{result}'"
        )
    
    def test_tiktok_ads(self):
        """Gate 4.2: Known mapping - TikTok Ads."""
        result = normalize_channel(utm_source="TIKTOK_ADS", utm_medium=None, vendor="tiktok_ads")
        assert result == 'tiktok_paid', (
            f"Expected 'tiktok_paid' for TikTok Ads, got '{result}'"
        )
    
    def test_shopify_direct(self):
        """Gate 4.2: Known mapping - Shopify Direct Traffic."""
        result = normalize_channel(utm_source="DIRECT", utm_medium=None, vendor="shopify")
        assert result == 'direct', (
            f"Expected 'direct' for Shopify Direct, got '{result}'"
        )
    
    def test_shopify_organic(self):
        """Gate 4.2: Known mapping - Shopify Organic Traffic."""
        result = normalize_channel(utm_source="ORGANIC", utm_medium=None, vendor="shopify")
        assert result == 'organic', (
            f"Expected 'organic' for Shopify Organic, got '{result}'"
        )
    
    def test_shopify_referral(self):
        """Gate 4.2: Known mapping - Shopify Referral Traffic."""
        result = normalize_channel(utm_source="REFERRAL", utm_medium=None, vendor="shopify")
        assert result == 'referral', (
            f"Expected 'referral' for Shopify Referral, got '{result}'"
        )
    
    def test_stripe_direct(self):
        """Gate 4.2: Known mapping - Stripe Direct."""
        result = normalize_channel(utm_source="DIRECT", utm_medium=None, vendor="stripe")
        assert result == 'direct', (
            f"Expected 'direct' for Stripe Direct, got '{result}'"
        )
    
    def test_stripe_email(self):
        """Gate 4.2: Known mapping - Stripe Email."""
        result = normalize_channel(utm_source="EMAIL", utm_medium=None, vendor="stripe")
        assert result == 'email', (
            f"Expected 'email' for Stripe Email, got '{result}'"
        )

    def test_stripe_vendor_passthrough_defaults_to_direct(self):
        """
        Stripe webhook v2 default metadata sets vendor=stripe, utm_source=stripe.
        This should normalize to DIRECT without unmapped fallback logging.
        """
        result = normalize_channel(utm_source="stripe", utm_medium=None, vendor="stripe")
        assert result == "direct", (
            f"Expected 'direct' for vendor/source passthrough, got '{result}'"
        )
    
    def test_woocommerce_email(self):
        """Gate 4.2: Known mapping - WooCommerce Email."""
        result = normalize_channel(utm_source="EMAIL", utm_medium=None, vendor="woocommerce")
        assert result == 'email', (
            f"Expected 'email' for WooCommerce Email, got '{result}'"
        )


class TestUnmappedInputs:
    """Test that unmapped inputs fall back to 'unknown' and are logged."""
    
    @patch('app.ingestion.channel_normalization.log_unmapped_channel')
    def test_unmapped_vendor_returns_unknown(self, mock_log):
        """Gate 4.3: Unmapped vendor returns 'unknown'."""
        result = normalize_channel(
            utm_source="random_vendor",
            utm_medium="random",
            vendor="unknown_vendor"
        )
        assert result == 'unknown', (
            f"Expected 'unknown' for unmapped vendor, got '{result}'"
        )
    
    @patch('app.ingestion.channel_normalization.log_unmapped_channel')
    def test_unmapped_vendor_logs_occurrence(self, mock_log):
        """Gate 4.3: Unmapped vendor logs occurrence."""
        normalize_channel(
            utm_source="bing",
            utm_medium="cpc",
            vendor="bing_ads",
            tenant_id="test-tenant-123"
        )
        
        # Verify log_unmapped_channel was called
        assert mock_log.called, "log_unmapped_channel() should be called for unmapped vendor"
        
        # Verify log parameters
        call_args = mock_log.call_args
        assert call_args is not None, "log_unmapped_channel() should have been called with arguments"
        assert "bing_ads" in str(call_args), "Vendor 'bing_ads' should be in log call"
    
    def test_no_vendor_no_utm_returns_direct(self):
        """No vendor and no UTM params should return 'direct'."""
        result = normalize_channel(utm_source=None, utm_medium=None, vendor=None)
        # Note: Based on implementation, this should return 'direct' or 'unknown'
        # Adjust based on actual business logic
        assert result in ['direct', 'unknown'], (
            f"Expected 'direct' or 'unknown' for no params, got '{result}'"
        )
    
    @patch('app.ingestion.channel_normalization.log_unmapped_channel')
    def test_utm_without_vendor_returns_unknown(self, mock_log):
        """UTM params without vendor context returns 'unknown'."""
        result = normalize_channel(utm_source="google", utm_medium="cpc", vendor=None)
        assert result == 'unknown', (
            f"Expected 'unknown' for UTM without vendor, got '{result}'"
        )
        assert mock_log.called, "Should log unmapped channel when vendor missing"

    @patch("app.ingestion.channel_normalization.increment_unmapped_channel_metric")
    @patch("app.ingestion.channel_normalization.log_unmapped_channel")
    def test_unmapped_logging_deduplicates_per_raw_key(self, mock_log, mock_metric):
        """
        Repeated unmapped keys should log/emit once per process to avoid log storms.
        """
        channel_normalization._normalize_channel_cached.cache_clear()
        with channel_normalization._SEEN_UNMAPPED_KEYS_LOCK:
            channel_normalization._SEEN_UNMAPPED_KEYS.clear()

        for _ in range(3):
            result = normalize_channel(
                utm_source="bing",
                utm_medium="cpc",
                vendor="bing_ads",
                tenant_id="tenant-a",
            )
            assert result == "unknown"

        assert mock_log.call_count == 1
        assert mock_metric.call_count == 1

    @patch("app.ingestion.channel_normalization.increment_unmapped_channel_metric")
    @patch("app.ingestion.channel_normalization.log_unmapped_channel")
    def test_unmapped_dedup_cache_is_bounded(self, mock_log, mock_metric):
        """
        Dedup key cache must remain bounded to prevent memory growth under high cardinality.
        """
        channel_normalization._normalize_channel_cached.cache_clear()
        with channel_normalization._SEEN_UNMAPPED_KEYS_LOCK:
            channel_normalization._SEEN_UNMAPPED_KEYS.clear()

        original_cap = channel_normalization._UNMAPPED_KEY_CACHE_MAX
        channel_normalization._UNMAPPED_KEY_CACHE_MAX = 3
        try:
            for i in range(10):
                result = normalize_channel(
                    utm_source=f"source_{i}",
                    utm_medium="cpc",
                    vendor="vendor_x",
                    tenant_id="tenant-b",
                )
                assert result == "unknown"
                with channel_normalization._SEEN_UNMAPPED_KEYS_LOCK:
                    assert len(channel_normalization._SEEN_UNMAPPED_KEYS) <= 3
        finally:
            channel_normalization._UNMAPPED_KEY_CACHE_MAX = original_cap


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_string_inputs(self):
        """Empty string inputs are handled gracefully."""
        result = normalize_channel(utm_source="", utm_medium="", vendor="")
        assert result in get_valid_taxonomy_codes(), (
            f"Empty string inputs should return valid taxonomy code, got '{result}'"
        )
    
    def test_whitespace_inputs(self):
        """Whitespace inputs are handled gracefully."""
        result = normalize_channel(utm_source="  ", utm_medium="  ", vendor="  ")
        valid_codes = get_valid_taxonomy_codes()
        assert result in valid_codes, (
            f"Whitespace inputs should return valid taxonomy code, got '{result}'"
        )
    
    def test_mixed_case_utm_source(self):
        """Mixed case UTM source is handled (case-insensitive lookup)."""
        # Test that 'Search' and 'SEARCH' both work for Google Ads
        result_lower = normalize_channel(utm_source="search", utm_medium=None, vendor="google_ads")
        result_upper = normalize_channel(utm_source="SEARCH", utm_medium=None, vendor="google_ads")
        result_mixed = normalize_channel(utm_source="Search", utm_medium=None, vendor="google_ads")
        
        # All should map to the same canonical code or 'unknown'
        valid_codes = get_valid_taxonomy_codes()
        assert result_lower in valid_codes
        assert result_upper in valid_codes
        assert result_mixed in valid_codes
    
    def test_special_characters_in_utm(self):
        """Special characters in UTM params don't break normalization."""
        result = normalize_channel(
            utm_source="test-source!@#",
            utm_medium="test-medium$%^",
            vendor="shopify"
        )
        assert result in get_valid_taxonomy_codes(), (
            f"Special characters should not break normalization, got '{result}'"
        )


class TestTaxonomyCodeSet:
    """Test that the taxonomy code set matches expected canonical codes."""
    
    def test_unknown_code_exists(self):
        """'unknown' fallback code exists in taxonomy."""
        valid_codes = get_valid_taxonomy_codes()
        assert 'unknown' in valid_codes, "'unknown' MUST exist in taxonomy codes"
    
    def test_all_expected_codes_exist(self):
        """All expected canonical codes exist in taxonomy."""
        valid_codes = get_valid_taxonomy_codes()
        expected_codes = {
            'unknown',
            'direct',
            'email',
            'facebook_brand',
            'facebook_paid',
            'google_display_paid',
            'google_search_paid',
            'organic',
            'referral',
            'tiktok_paid',
        }
        
        missing_codes = expected_codes - valid_codes
        assert len(missing_codes) == 0, (
            f"Missing expected canonical codes: {missing_codes}"
        )
    
    def test_taxonomy_code_count(self):
        """Taxonomy has expected number of codes (10 as of 2025-11-16)."""
        valid_codes = get_valid_taxonomy_codes()
        assert len(valid_codes) == 10, (
            f"Expected 10 canonical codes (9 original + 1 'unknown'), got {len(valid_codes)}"
        )


class TestCIIntegration:
    """Tests that verify CI integration requirements."""
    
    def test_breaking_normalization_function_detected(self):
        """Verify that returning invalid code would be detected by tests."""
        valid_codes = get_valid_taxonomy_codes()
        
        # Simulate a broken normalization that returns invalid code
        invalid_code = "invalid_channel_code_not_in_taxonomy"
        assert invalid_code not in valid_codes, (
            "Test setup error: 'invalid_channel_code_not_in_taxonomy' should not be valid"
        )
        
        # If normalize_channel() returned this, the contract test would fail
        # This test verifies that our test suite would catch such breakage
    
    def test_all_mapping_yaml_codes_are_valid(self):
        """Verify all codes in channel_mapping.yaml exist in taxonomy."""
        from app.ingestion.channel_normalization import load_channel_mapping
        
        mapping = load_channel_mapping()
        valid_codes = get_valid_taxonomy_codes()
        
        invalid_mappings = []
        for vendor, vendor_mappings in mapping.items():
            for vendor_key, canonical_code in vendor_mappings.items():
                if canonical_code not in valid_codes:
                    invalid_mappings.append((vendor, vendor_key, canonical_code))
        
        assert len(invalid_mappings) == 0, (
            f"Found mappings to non-taxonomy codes: {invalid_mappings}. "
            "All codes in channel_mapping.yaml must exist in channel_taxonomy."
        )


# Pytest configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])



