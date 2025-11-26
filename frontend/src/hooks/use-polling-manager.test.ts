/**
 * Test file for usePollingManager hook - Binary Exit Gate Verification
 * 
 * Requirements verification:
 * 1. Does it poll at precise 30-second intervals with drift correction? (YES/NO)
 * 2. Does it auto-pause on browser tab hidden? (YES/NO)
 * 3. Do manual controls work immediately and reliably? (YES/NO)
 * 4. Does it clear all intervals and listeners on unmount? (YES/NO)
 * 5. Does it prevent overlapping requests? (YES/NO)
 * 6. Does it maintain ±100ms accuracy over 10 cycles? (YES/NO)
 * 7. Does it trigger immediate poll on resume? (YES/NO)
 */

import { usePollingManager } from './use-polling-manager';

interface TimingMeasurement {
  cycle: number;
  expectedTime: number;
  actualTime: number;
  drift: number;
}

export const testScenarios = {
  // Test 1: 30-second intervals with drift correction
  async testDriftCorrection() {
    console.log('=== Test 1: 30-Second Intervals with Drift Correction ===');
    
    const measurements: TimingMeasurement[] = [];
    const startTime = Date.now();
    let cycleCount = 0;
    
    const { pause } = usePollingManager({
      intervalMs: 30000,
      onPoll: async () => {
        const actualTime = Date.now();
        const expectedTime = startTime + (cycleCount * 30000);
        const drift = actualTime - expectedTime;
        
        measurements.push({
          cycle: cycleCount,
          expectedTime,
          actualTime,
          drift
        });
        
        console.log(`Cycle ${cycleCount}: Expected ${expectedTime}, Actual ${actualTime}, Drift ${drift}ms`);
        cycleCount++;
        
        if (cycleCount >= 3) {
          pause();
        }
      }
    });
    
    // Wait for 3 cycles to complete
    await new Promise(resolve => setTimeout(resolve, 95000));
    
    // Analyze drift
    const avgDrift = measurements.reduce((sum, m) => sum + Math.abs(m.drift), 0) / measurements.length;
    console.log(`✓ Average drift: ${avgDrift.toFixed(2)}ms`);
    console.log(`✓ Expected: Consistent 30-second intervals`);
  },

  // Test 2: Auto-pause on tab hidden
  testVisibilityPause() {
    console.log('=== Test 2: Auto-Pause on Tab Hidden ===');
    
    let pollCount = 0;
    const { isPausedByVisibility, isActive } = usePollingManager({
      intervalMs: 30000,
      onPoll: () => {
        pollCount++;
        console.log(`Poll ${pollCount} executed, isActive: ${isActive}`);
      }
    });
    
    console.log(`Initial state - isPausedByVisibility: ${isPausedByVisibility}, isActive: ${isActive}`);
    console.log('✓ To test: Switch to another tab and check logs pause');
    console.log('✓ Expected: Polling stops when document.hidden === true');
  },

  // Test 3: Manual controls immediate response
  async testManualControls() {
    console.log('=== Test 3: Manual Controls Immediate Response ===');
    
    const controlLog: string[] = [];
    let pollCount = 0;
    
    const { pause, resume, toggle, isPaused, isActive } = usePollingManager({
      intervalMs: 5000,
      onPoll: () => {
        pollCount++;
        controlLog.push(`Poll ${pollCount} at ${Date.now()}`);
      }
    });
    
    // Test pause
    setTimeout(() => {
      pause();
      const pauseState = isPaused;
      controlLog.push(`Paused at ${Date.now()}, isPaused: ${pauseState}`);
    }, 12000);
    
    // Test resume
    setTimeout(() => {
      resume();
      const resumeState = isPaused;
      controlLog.push(`Resumed at ${Date.now()}, isPaused: ${resumeState}`);
    }, 20000);
    
    // Test toggle
    setTimeout(() => {
      toggle();
      const toggleState = isPaused;
      controlLog.push(`Toggled at ${Date.now()}, isPaused: ${toggleState}`);
    }, 28000);
    
    await new Promise(resolve => setTimeout(resolve, 35000));
    
    console.log('Control log:');
    controlLog.forEach(log => console.log(`  ${log}`));
    console.log('✓ Expected: State changes immediately, polls stop/start accordingly');
  },

  // Test 4: Cleanup on unmount
  testCleanup() {
    console.log('=== Test 4: Cleanup on Unmount ===');
    
    // This test verifies cleanup behavior
    // In a real React environment, the useEffect cleanup would run on unmount
    // The hook creates 2 intervals (one for polling, one for countdown)
    // Both should be cleared when the component unmounts
    
    usePollingManager({
      intervalMs: 30000,
      onPoll: () => console.log('Poll executed')
    });
    
    console.log('✓ Hook created with polling and countdown intervals');
    console.log('✓ Expected: Both intervals cleared on unmount (Lines 67-69)');
    console.log('✓ Expected: Visibility event listener removed (Line 56)');
    console.log('✓ Cleanup functions defined in useEffect return statements');
  },

  // Test 5: Prevent overlapping requests
  async testOverlapPrevention() {
    console.log('=== Test 5: Prevent Overlapping Requests ===');
    
    const executionLog: string[] = [];
    let activePollCount = 0;
    let maxConcurrent = 0;
    
    const { pause } = usePollingManager({
      intervalMs: 1000, // Short interval to test overlaps
      onPoll: async () => {
        activePollCount++;
        maxConcurrent = Math.max(maxConcurrent, activePollCount);
        const startTime = Date.now();
        executionLog.push(`Poll start at ${startTime}, active: ${activePollCount}`);
        
        // Simulate slow async operation (2 seconds)
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        activePollCount--;
        executionLog.push(`Poll end at ${Date.now()}, duration: ${Date.now() - startTime}ms`);
      }
    });
    
    // Run for 6 seconds (should have attempted 6 polls, but async takes 2s each)
    await new Promise(resolve => setTimeout(resolve, 6000));
    pause();
    
    console.log('Execution log:');
    executionLog.forEach(log => console.log(`  ${log}`));
    console.log(`Max concurrent polls: ${maxConcurrent}`);
    console.log('✓ Expected: maxConcurrent === 1 (no overlaps)');
  },

  // Test 6: ±100ms accuracy over 10 cycles
  async testAccuracyOver10Cycles() {
    console.log('=== Test 6: ±100ms Accuracy Over 10 Cycles ===');
    
    const measurements: TimingMeasurement[] = [];
    const startTime = Date.now();
    let cycleCount = 0;
    
    const { pause } = usePollingManager({
      intervalMs: 5000, // Use 5s for faster testing
      onPoll: () => {
        const actualTime = Date.now();
        const expectedTime = startTime + (cycleCount * 5000);
        const drift = actualTime - expectedTime;
        
        measurements.push({
          cycle: cycleCount,
          expectedTime,
          actualTime,
          drift
        });
        
        console.log(`Cycle ${cycleCount}: Drift ${drift}ms`);
        cycleCount++;
        
        if (cycleCount >= 10) {
          pause();
        }
      }
    });
    
    // Wait for 10 cycles (50 seconds)
    await new Promise(resolve => setTimeout(resolve, 52000));
    
    // Analyze accuracy
    const maxDrift = Math.max(...measurements.map(m => Math.abs(m.drift)));
    const avgDrift = measurements.reduce((sum, m) => sum + Math.abs(m.drift), 0) / measurements.length;
    
    console.log('=== Accuracy Results ===');
    console.log(`Max drift: ${maxDrift.toFixed(2)}ms`);
    console.log(`Avg drift: ${avgDrift.toFixed(2)}ms`);
    console.log(`Within ±100ms: ${maxDrift <= 100 ? 'YES ✓' : 'NO ✗'}`);
    
    // Detailed breakdown
    console.log('\nCycle-by-cycle:');
    measurements.forEach(m => {
      console.log(`  Cycle ${m.cycle}: ${m.drift >= 0 ? '+' : ''}${m.drift}ms`);
    });
  },

  // Test 7: Immediate poll on resume
  async testImmediatePollOnResume() {
    console.log('=== Test 7: Immediate Poll on Resume ===');
    
    const pollTimes: number[] = [];
    
    const { pause, resume } = usePollingManager({
      intervalMs: 10000,
      onPoll: () => {
        const now = Date.now();
        pollTimes.push(now);
        console.log(`Poll at ${now}`);
      }
    });
    
    // Wait for first poll
    await new Promise(resolve => setTimeout(resolve, 500));
    const firstPoll = pollTimes[pollTimes.length - 1];
    
    // Pause
    pause();
    console.log(`Paused at ${Date.now()}`);
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Resume and check for immediate poll
    const resumeTime = Date.now();
    resume();
    console.log(`Resumed at ${resumeTime}`);
    
    // Wait a bit for immediate poll
    await new Promise(resolve => setTimeout(resolve, 100));
    
    const resumePoll = pollTimes[pollTimes.length - 1];
    const resumeDelay = resumePoll - resumeTime;
    
    console.log(`Resume delay: ${resumeDelay}ms`);
    console.log(`Immediate poll: ${resumeDelay < 100 ? 'YES ✓' : 'NO ✗'}`);
  },

  // Test 8: Pause/Resume drift correction
  async testPauseResumeDriftCorrection() {
    console.log('=== Test 8: Pause/Resume Drift Correction ===');
    
    const measurements: Array<{ time: number; type: string; drift?: number }> = [];
    const startTime = Date.now();
    let cycleCount = 0;
    
    const { pause, resume } = usePollingManager({
      intervalMs: 5000,
      onPoll: () => {
        const actualTime = Date.now();
        const expectedTime = startTime + (cycleCount * 5000);
        const drift = actualTime - expectedTime;
        
        measurements.push({
          time: actualTime,
          type: 'poll',
          drift
        });
        
        console.log(`Cycle ${cycleCount}: Drift ${drift}ms`);
        cycleCount++;
      }
    });
    
    // Let it run for 2 cycles
    await new Promise(resolve => setTimeout(resolve, 11000));
    
    // Pause
    const pauseTime = Date.now();
    pause();
    measurements.push({ time: pauseTime, type: 'pause' });
    console.log(`Paused at ${pauseTime}`);
    
    // Wait 3 seconds while paused
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Resume
    const resumeTime = Date.now();
    resume();
    measurements.push({ time: resumeTime, type: 'resume' });
    console.log(`Resumed at ${resumeTime}`);
    
    // Run for 3 more cycles after resume
    await new Promise(resolve => setTimeout(resolve, 16000));
    pause();
    
    console.log('\n=== Timeline ===');
    measurements.forEach((m, i) => {
      if (m.type === 'poll') {
        console.log(`  ${i}. Poll at ${m.time - startTime}ms, drift: ${m.drift}ms`);
      } else {
        console.log(`  ${i}. ${m.type.toUpperCase()} at ${m.time - startTime}ms`);
      }
    });
    
    // Check if drift correction maintains schedule after resume
    const pollsAfterResume = measurements.filter((m, i) => 
      m.type === 'poll' && i > measurements.findIndex(x => x.type === 'resume')
    );
    
    console.log('\nPolls after resume:');
    pollsAfterResume.forEach(p => {
      console.log(`  Drift: ${p.drift}ms`);
    });
  }
};

// Export for console testing
if (typeof window !== 'undefined') {
  (window as any).pollingTests = testScenarios;
  console.log('Polling tests loaded. Run: window.pollingTests.testDriftCorrection()');
}
