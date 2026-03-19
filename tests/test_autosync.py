#!/usr/bin/env python3
"""
Tests for the autosync module.
"""
import pytest
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from autosync import (
    parse_time,
    format_time,
    DriftConfig,
    apply_drift_correction,
    parse_srt_line,
    COMMON_DRIFT_RATES
)


class TestParseTime:
    """Tests for parse_time function."""
    
    def test_parse_hh_mm_ss_mmm(self):
        """Test parsing HH:MM:SS,mmm format."""
        assert parse_time("00:00:30,500") == 30500.0
        assert parse_time("00:01:30,000") == 90000.0
        assert parse_time("01:30:00,000") == 5400000.0
    
    def test_parse_hh_mm_ss_period(self):
        """Test parsing HH:MM:SS.mmm format (period instead of comma)."""
        assert parse_time("00:00:30.500") == 30500.0
        assert parse_time("00:01:30.000") == 90000.0
    
    def test_parse_hh_mm_ss_no_ms(self):
        """Test parsing HH:MM:SS without milliseconds."""
        assert parse_time("00:00:30") == 30000.0
        assert parse_time("00:01:30") == 90000.0
    
    def test_parse_mm_ss(self):
        """Test parsing MM:SS format."""
        assert parse_time("01:30") == 90000.0
        assert parse_time("01:30,500") == 90500.0
    
    def test_parse_seconds(self):
        """Test parsing plain seconds."""
        assert parse_time("30") == 30000.0
        assert parse_time("30.5") == 30500.0
        assert parse_time("30.500") == 30500.0


class TestFormatTime:
    """Tests for format_time function."""
    
    def test_format_basic(self):
        """Test basic formatting."""
        assert format_time(30500.0) == "00:00:30,500"
        assert format_time(90000.0) == "00:01:30,000"
        assert format_time(5400000.0) == "01:30:00,000"
    
    def test_format_zero(self):
        """Test formatting zero."""
        assert format_time(0) == "00:00:00,000"
    
    def test_format_negative(self):
        """Test formatting negative (should clamp to zero)."""
        assert format_time(-100) == "00:00:00,000"
    
    def test_format_rounding(self):
        """Test formatting with rounding."""
        assert format_time(30500.5) == "00:00:30,500"


class TestDriftConfig:
    """Tests for DriftConfig class."""
    
    def test_two_point_drift_rate(self):
        """Test drift rate calculation for two-point mode."""
        config = DriftConfig(
            reference_time=30000,  # 0:30
            offset_time=600000,    # 10:00
            offset_at_offset_time=5000  # 5 seconds late
        )
        # Drift rate = 5000 / (600000 - 30000) = 5000 / 570000 = 0.00877...
        assert abs(config.drift_rate - 0.00877193) < 0.00001
    
    def test_two_point_offset_at_time(self):
        """Test offset calculation at various times."""
        config = DriftConfig(
            reference_time=30000,  # 0:30 - correct
            offset_time=600000,    # 10:00
            offset_at_offset_time=5000  # 5 seconds late
        )
        
        # At reference time, offset should be 0
        assert config.get_offset_at_time(30000) == 0
        
        # At offset time, offset should be 5000
        assert config.get_offset_at_time(600000) == 5000
        
        # At midpoint (5:15 = 315000ms), offset should be ~2.5 seconds
        offset_at_midpoint = config.get_offset_at_time(315000)
        assert abs(offset_at_midpoint - 2500) < 100  # Allow some rounding
    
    def test_multi_point_drift(self):
        """Test multi-point drift correction."""
        sync_points = [
            (30000, 0),      # 0:30 - correct
            (300000, 2500),  # 5:00 - 2.5 seconds late
            (600000, 5000)   # 10:00 - 5 seconds late
        ]
        config = DriftConfig(
            reference_time=30000,
            offset_time=600000,
            offset_at_offset_time=5000,
            sync_points=sync_points
        )
        
        # At each sync point, should match exactly
        assert config.get_offset_at_time(30000) == 0
        assert config.get_offset_at_time(300000) == 2500
        assert config.get_offset_at_time(600000) == 5000
        
        # Between points should interpolate
        # At 2:30 (150000ms), between 0:30 (30000ms, offset=0) and 5:00 (300000ms, offset=2500)
        # ratio = (150000 - 30000) / (300000 - 30000) = 120000 / 270000 = 0.444...
        # offset = 0 + 0.444 * 2500 = 1111.11...
        offset_at_2_30 = config.get_offset_at_time(150000)  # 2:30
        assert abs(offset_at_2_30 - 1111.11) < 10  # ~1.11 seconds


class TestApplyDriftCorrection:
    """Tests for apply_drift_correction function."""
    
    def test_simple_drift_correction(self):
        """Test basic drift correction."""
        srt_content = """1
00:00:30,000 --> 00:00:32,000
Hello world

2
00:05:00,000 --> 00:05:02,000
This is a test

3
00:10:00,000 --> 00:10:02,000
End of test
"""
        config = DriftConfig(
            reference_time=30000,  # 0:30 - correct
            offset_time=600000,    # 10:00
            offset_at_offset_time=5000  # 5 seconds late
        )
        
        result = apply_drift_correction(srt_content, config)
        
        # First subtitle at 0:30 should have start unchanged (reference point)
        # but end time at 0:32 will have a small offset
        assert "00:00:30,000 -->" in result
        
        # Second subtitle at 5:00 should have ~2.37 second offset
        # Original: 00:05:00,000 --> 00:05:02,000
        # Expected: ~00:05:02,368 --> ~00:05:04,386
        assert "00:05:02" in result
        
        # Third subtitle at 10:00 should have 5 second offset
        # Original: 00:10:00,000 --> 00:10:02,000
        # Expected: 00:10:05,000 --> 00:10:07,018 (end also gets offset)
        assert "00:10:05,000 -->" in result
    
    def test_negative_drift(self):
        """Test negative drift (subtitles are early)."""
        srt_content = """1
00:00:00,000 --> 00:00:02,000
Start

2
00:10:00,000 --> 00:10:02,000
Ten minutes
"""
        config = DriftConfig(
            reference_time=0,
            offset_time=600000,
            offset_at_offset_time=-3000  # 3 seconds early
        )
        
        result = apply_drift_correction(srt_content, config)
        
        # First subtitle at 0:00 should have start unchanged (reference point)
        # but end time at 0:02 will have a small negative offset
        assert "00:00:00,000 -->" in result
        
        # Second subtitle should be shifted earlier by 3 seconds
        # Original: 00:10:00,000 --> 00:10:02,000
        # Expected: 00:09:57,000 --> 00:09:58,990 (end also gets offset)
        assert "00:09:57,000 -->" in result
    
    def test_clamp_to_zero(self):
        """Test that negative timestamps are clamped to zero."""
        srt_content = """1
00:00:01,000 --> 00:00:03,000
Early subtitle
"""
        # Create a config that would produce negative timestamps
        # At 0:01 (1000ms), with reference at 0:10 (10000ms) and -50s offset at 10:00
        # drift_rate = -50000 / (600000 - 10000) = -50000 / 590000 = -0.0847...
        # offset at 1000ms = -0.0847 * (1000 - 10000) = -0.0847 * -9000 = +763ms
        # So the timestamp would be 1000 + 763 = 1763ms, which is positive
        # Let's use a more extreme case
        config = DriftConfig(
            reference_time=1000,  # 0:01
            offset_time=10000,    # 0:10
            offset_at_offset_time=-20000  # -20 seconds at 0:10
        )
        # drift_rate = -20000 / (10000 - 1000) = -20000 / 9000 = -2.22...
        # offset at 500ms = -2.22 * (500 - 1000) = -2.22 * -500 = +1111ms
        # Hmm, still positive. Let's try a subtitle AFTER the reference point
        
        srt_content2 = """1
00:00:05,000 --> 00:00:07,000
Early subtitle
"""
        # At 5000ms, offset = -2.22 * (5000 - 1000) = -2.22 * 4000 = -8888ms
        # 5000 - 8888 = -3888ms, which would be clamped to 0
        result = apply_drift_correction(srt_content2, config, clamp_to_zero=True)
        
        # Should be clamped to zero, not negative
        assert "00:00:00,000" in result
    
    def test_preserve_line_endings(self):
        """Test that line endings are preserved."""
        srt_content = "1\r\n00:00:00,000 --> 00:00:02,000\r\nTest\r\n\r\n"
        
        config = DriftConfig(
            reference_time=0,
            offset_time=1000,
            offset_at_offset_time=0
        )
        
        result = apply_drift_correction(srt_content, config, preserve_line_endings=True)
        
        # Should preserve \r\n
        assert "\r\n" in result


class TestParseSrtLine:
    """Tests for parse_srt_line function."""
    
    def test_valid_timestamp_line(self):
        """Test parsing valid timestamp line."""
        result = parse_srt_line("00:00:01,000 --> 00:00:03,500")
        assert result == ("00:00:01,000", "00:00:03,500")
    
    def test_invalid_line(self):
        """Test parsing invalid line."""
        assert parse_srt_line("1") is None
        assert parse_srt_line("Hello world") is None
        assert parse_srt_line("") is None
    
    def test_malformed_timestamp(self):
        """Test parsing malformed timestamp."""
        assert parse_srt_line("invalid --> timestamp") is None


class TestCommonDriftRates:
    """Tests for common drift rates."""
    
    def test_common_rates_exist(self):
        """Test that common drift rates are defined."""
        assert "23.976_to_24" in COMMON_DRIFT_RATES
        assert "24_to_23.976" in COMMON_DRIFT_RATES
        assert "29.97_to_30" in COMMON_DRIFT_RATES
        assert "30_to_29.97" in COMMON_DRIFT_RATES
    
    def test_drift_rate_values(self):
        """Test that drift rates have reasonable values."""
        # 23.976 to 24 should be about 0.1% drift
        rate = COMMON_DRIFT_RATES["23.976_to_24"]
        assert 0.0009 < rate < 0.0011
        
        # Reverse should be negative
        assert COMMON_DRIFT_RATES["24_to_23.976"] < 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
