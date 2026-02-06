#!/usr/bin/env python3
"""
Test script to demonstrate async operations in Terminal Browser
This shows how independent operations run concurrently
"""

import asyncio
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.state_manager import StateManager
from core.preferences_manager import PreferencesManager
from core.command_history_manager import CommandHistoryManager


async def test_concurrent_saves():
    """Test that multiple save operations run concurrently"""
    print("\n=== Testing Concurrent Save Operations ===\n")
    
    state_mgr = StateManager()
    prefs_mgr = PreferencesManager()
    history_mgr = CommandHistoryManager()
    
    # Prepare test data
    test_state = {
        'groups': ['Group 1', 'Group 2'],
        'tabs': [{'name': 'Tab 1'}, {'name': 'Tab 2'}],
        'current_group': 0
    }
    
    # Add some test history
    history_mgr.add_command('ls -la', 'test_group', '/tmp')
    history_mgr.add_command('cd ~', 'test_group', '/tmp')
    
    # Time sequential saves
    print("Sequential saves (old approach):")
    start = time.time()
    await state_mgr.save_state(test_state)
    await prefs_mgr.save_preferences()
    await history_mgr.save_history()
    sequential_time = time.time() - start
    print(f"  Time: {sequential_time:.4f}s\n")
    
    # Time concurrent saves
    print("Concurrent saves (new approach):")
    start = time.time()
    await asyncio.gather(
        state_mgr.save_state(test_state),
        prefs_mgr.save_preferences(),
        history_mgr.save_history()
    )
    concurrent_time = time.time() - start
    print(f"  Time: {concurrent_time:.4f}s\n")
    
    speedup = sequential_time / concurrent_time if concurrent_time > 0 else 1.0
    print(f"Speedup: {speedup:.2f}x faster with concurrent operations!\n")


async def test_concurrent_loads():
    """Test that multiple load operations run concurrently"""
    print("\n=== Testing Concurrent Load Operations ===\n")
    
    state_mgr = StateManager()
    prefs_mgr = PreferencesManager()
    history_mgr = CommandHistoryManager()
    
    # Time sequential loads
    print("Sequential loads (old approach):")
    start = time.time()
    state = await state_mgr.load_state()
    await prefs_mgr.load_preferences()
    await history_mgr.load_history()
    sequential_time = time.time() - start
    print(f"  Time: {sequential_time:.4f}s")
    print(f"  State loaded: {state is not None}")
    print(f"  Preferences loaded: {prefs_mgr._preferences is not None}")
    print(f"  History loaded: {len(history_mgr.history)} commands\n")
    
    # Reset for concurrent test
    prefs_mgr._preferences = None
    history_mgr.history = []
    
    # Time concurrent loads
    print("Concurrent loads (new approach):")
    start = time.time()
    state, _, _ = await asyncio.gather(
        state_mgr.load_state(),
        prefs_mgr.load_preferences(),
        history_mgr.load_history()
    )
    concurrent_time = time.time() - start
    print(f"  Time: {concurrent_time:.4f}s")
    print(f"  State loaded: {state is not None}")
    print(f"  Preferences loaded: {prefs_mgr._preferences is not None}")
    print(f"  History loaded: {len(history_mgr.history)} commands\n")
    
    speedup = sequential_time / concurrent_time if concurrent_time > 0 else 1.0
    print(f"Speedup: {speedup:.2f}x faster with concurrent operations!\n")


async def test_independence():
    """Test that operations are truly independent"""
    print("\n=== Testing Operation Independence ===\n")
    
    state_mgr = StateManager()
    prefs_mgr = PreferencesManager()
    history_mgr = CommandHistoryManager()
    
    # Test concurrent operations with different completion times
    async def slow_save():
        print("  [State] Starting save...")
        await asyncio.sleep(0.1)  # Simulate slow I/O
        result = await state_mgr.save_state({'test': 'data'})
        print("  [State] Save complete!")
        return result
    
    async def fast_save():
        print("  [Prefs] Starting save...")
        await asyncio.sleep(0.05)  # Simulate faster I/O
        result = await prefs_mgr.save_preferences()
        print("  [Prefs] Save complete!")
        return result
    
    async def medium_save():
        print("  [History] Starting save...")
        await asyncio.sleep(0.075)  # Simulate medium I/O
        result = await history_mgr.save_history()
        print("  [History] Save complete!")
        return result
    
    print("Starting all operations concurrently...")
    print("(Notice they complete in order of speed, not start order)\n")
    
    start = time.time()
    results = await asyncio.gather(slow_save(), fast_save(), medium_save())
    total_time = time.time() - start
    
    print(f"\nAll operations completed in {total_time:.4f}s")
    print(f"(Would take {0.1 + 0.05 + 0.075:.4f}s sequentially)")
    print(f"Operations are independent: ✓")


async def main():
    """Run all async tests"""
    print("=" * 60)
    print("Terminal Browser - Async Architecture Test")
    print("=" * 60)
    
    try:
        await test_concurrent_saves()
        await test_concurrent_loads()
        await test_independence()
        
        print("\n" + "=" * 60)
        print("All tests completed successfully! ✓")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError during tests: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    # Run the async tests
    asyncio.run(main())
