#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Performance benchmark for unified MCP interface."""

import asyncio
import time
import statistics
import sys
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError
from aether_frame.tools.mcp.config import MCPServerConfig


@dataclass
class BenchmarkResult:
    """Performance benchmark result."""
    test_name: str
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    std_dev: float
    operations_count: int
    operations_per_second: float
    success_rate: float
    errors: List[str]


class MCPPerformanceBenchmark:
    """Performance benchmark suite for MCP unified interface."""
    
    def __init__(self):
        self.results: List[BenchmarkResult] = []
    
    async def benchmark_synchronous_calls(self, client: MCPClient, iterations: int = 50) -> BenchmarkResult:
        """Benchmark synchronous tool calls."""
        print(f"🔧 Benchmarking synchronous calls ({iterations} iterations)...")
        
        times = []
        errors = []
        success_count = 0
        
        for i in range(iterations):
            try:
                start_time = time.time()
                result = await client.call_tool("echo", {"text": f"Benchmark {i}"})
                end_time = time.time()
                
                execution_time = end_time - start_time
                times.append(execution_time)
                success_count += 1
                
                if i % 10 == 0:
                    print(f"  Progress: {i}/{iterations} ({execution_time:.3f}s)")
                    
            except Exception as e:
                errors.append(f"Iteration {i}: {str(e)}")
        
        # Calculate statistics
        total_time = sum(times)
        avg_time = statistics.mean(times) if times else 0
        min_time = min(times) if times else 0
        max_time = max(times) if times else 0
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        ops_per_sec = success_count / total_time if total_time > 0 else 0
        success_rate = success_count / iterations
        
        return BenchmarkResult(
            test_name="Synchronous Tool Calls",
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            std_dev=std_dev,
            operations_count=success_count,
            operations_per_second=ops_per_sec,
            success_rate=success_rate,
            errors=errors
        )
    
    async def benchmark_streaming_calls(self, client: MCPClient, iterations: int = 30) -> BenchmarkResult:
        """Benchmark streaming tool calls."""
        print(f"🌊 Benchmarking streaming calls ({iterations} iterations)...")
        
        times = []
        errors = []
        success_count = 0
        total_chunks = 0
        
        for i in range(iterations):
            try:
                start_time = time.time()
                chunk_count = 0
                
                async for chunk in client.call_tool_stream("echo", {"text": f"Stream benchmark {i}"}):
                    chunk_count += 1
                
                end_time = time.time()
                execution_time = end_time - start_time
                times.append(execution_time)
                total_chunks += chunk_count
                success_count += 1
                
                if i % 5 == 0:
                    print(f"  Progress: {i}/{iterations} ({execution_time:.3f}s, {chunk_count} chunks)")
                    
            except Exception as e:
                errors.append(f"Stream iteration {i}: {str(e)}")
        
        # Calculate statistics
        total_time = sum(times)
        avg_time = statistics.mean(times) if times else 0
        min_time = min(times) if times else 0
        max_time = max(times) if times else 0
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        ops_per_sec = success_count / total_time if total_time > 0 else 0
        success_rate = success_count / iterations
        
        result = BenchmarkResult(
            test_name="Streaming Tool Calls",
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            std_dev=std_dev,
            operations_count=success_count,
            operations_per_second=ops_per_sec,
            success_rate=success_rate,
            errors=errors
        )
        
        print(f"  📊 Average chunks per call: {total_chunks / success_count if success_count > 0 else 0:.1f}")
        
        return result
    
    async def benchmark_concurrent_calls(self, client: MCPClient, concurrent_count: int = 10, iterations: int = 5) -> BenchmarkResult:
        """Benchmark concurrent tool calls."""
        print(f"🔄 Benchmarking concurrent calls ({concurrent_count} concurrent, {iterations} iterations)...")
        
        times = []
        errors = []
        success_count = 0
        
        for i in range(iterations):
            try:
                start_time = time.time()
                
                # Create concurrent tasks
                tasks = [
                    client.call_tool("add", {"a": j, "b": j + 1})
                    for j in range(concurrent_count)
                ]
                
                # Execute concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                end_time = time.time()
                execution_time = end_time - start_time
                times.append(execution_time)
                
                # Count successes
                iteration_success = sum(1 for r in results if not isinstance(r, Exception))
                success_count += iteration_success
                
                # Track errors
                for j, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Concurrent iteration {i}, task {j}: {str(result)}")
                
                print(f"  Progress: {i}/{iterations} ({execution_time:.3f}s, {iteration_success}/{concurrent_count} succeeded)")
                
            except Exception as e:
                errors.append(f"Concurrent iteration {i}: {str(e)}")
        
        # Calculate statistics
        total_time = sum(times)
        avg_time = statistics.mean(times) if times else 0
        min_time = min(times) if times else 0
        max_time = max(times) if times else 0
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        total_operations = iterations * concurrent_count
        ops_per_sec = success_count / total_time if total_time > 0 else 0
        success_rate = success_count / total_operations
        
        return BenchmarkResult(
            test_name=f"Concurrent Calls ({concurrent_count} concurrent)",
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            std_dev=std_dev,
            operations_count=success_count,
            operations_per_second=ops_per_sec,
            success_rate=success_rate,
            errors=errors
        )
    
    async def benchmark_mixed_workload(self, client: MCPClient, iterations: int = 20) -> BenchmarkResult:
        """Benchmark mixed synchronous and streaming workload."""
        print(f"🔀 Benchmarking mixed workload ({iterations} iterations)...")
        
        times = []
        errors = []
        success_count = 0
        
        for i in range(iterations):
            try:
                start_time = time.time()
                
                # Mix of synchronous and streaming calls
                tasks = [
                    # Synchronous calls
                    client.call_tool("echo", {"text": f"Mixed sync {i}"}),
                    client.call_tool("add", {"a": i, "b": i * 2}),
                    # Streaming calls (collect results)
                    self._collect_stream_result(client.call_tool_stream("echo", {"text": f"Mixed stream {i}"}))
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                end_time = time.time()
                execution_time = end_time - start_time
                times.append(execution_time)
                
                # Count successes
                iteration_success = sum(1 for r in results if not isinstance(r, Exception))
                success_count += iteration_success
                
                # Track errors
                for j, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Mixed iteration {i}, task {j}: {str(result)}")
                
                if i % 5 == 0:
                    print(f"  Progress: {i}/{iterations} ({execution_time:.3f}s, {iteration_success}/3 succeeded)")
                
            except Exception as e:
                errors.append(f"Mixed iteration {i}: {str(e)}")
        
        # Calculate statistics
        total_time = sum(times)
        avg_time = statistics.mean(times) if times else 0
        min_time = min(times) if times else 0
        max_time = max(times) if times else 0
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        total_operations = iterations * 3  # 3 operations per iteration
        ops_per_sec = success_count / total_time if total_time > 0 else 0
        success_rate = success_count / total_operations
        
        return BenchmarkResult(
            test_name="Mixed Workload (Sync + Stream)",
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            std_dev=std_dev,
            operations_count=success_count,
            operations_per_second=ops_per_sec,
            success_rate=success_rate,
            errors=errors
        )
    
    async def _collect_stream_result(self, stream):
        """Helper to collect streaming result."""
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
        return chunks
    
    async def benchmark_tool_discovery(self, client: MCPClient, iterations: int = 20) -> BenchmarkResult:
        """Benchmark tool discovery performance."""
        print(f"📋 Benchmarking tool discovery ({iterations} iterations)...")
        
        times = []
        errors = []
        success_count = 0
        
        for i in range(iterations):
            try:
                start_time = time.time()
                tools = await client.discover_tools()
                end_time = time.time()
                
                execution_time = end_time - start_time
                times.append(execution_time)
                success_count += 1
                
                if i % 5 == 0:
                    print(f"  Progress: {i}/{iterations} ({execution_time:.3f}s, {len(tools)} tools)")
                    
            except Exception as e:
                errors.append(f"Discovery iteration {i}: {str(e)}")
        
        # Calculate statistics
        total_time = sum(times)
        avg_time = statistics.mean(times) if times else 0
        min_time = min(times) if times else 0
        max_time = max(times) if times else 0
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        ops_per_sec = success_count / total_time if total_time > 0 else 0
        success_rate = success_count / iterations
        
        return BenchmarkResult(
            test_name="Tool Discovery",
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            std_dev=std_dev,
            operations_count=success_count,
            operations_per_second=ops_per_sec,
            success_rate=success_rate,
            errors=errors
        )
    
    def print_result(self, result: BenchmarkResult):
        """Print benchmark result."""
        print(f"\n📊 {result.test_name} Results:")
        print(f"  Total Time: {result.total_time:.3f}s")
        print(f"  Average Time: {result.avg_time:.3f}s")
        print(f"  Min/Max Time: {result.min_time:.3f}s / {result.max_time:.3f}s")
        print(f"  Std Deviation: {result.std_dev:.3f}s")
        print(f"  Operations: {result.operations_count}")
        print(f"  Ops/Second: {result.operations_per_second:.2f}")
        print(f"  Success Rate: {result.success_rate:.1%}")
        
        if result.errors:
            print(f"  Errors ({len(result.errors)}):")
            for error in result.errors[:3]:  # Show first 3 errors
                print(f"    - {error}")
            if len(result.errors) > 3:
                print(f"    ... and {len(result.errors) - 3} more")
    
    def print_summary(self):
        """Print benchmark summary."""
        print("\n" + "=" * 60)
        print("📈 PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 60)
        
        if not self.results:
            print("No benchmark results to display")
            return
        
        # Summary table
        print(f"{'Test Name':<30} {'Avg Time':<12} {'Ops/Sec':<10} {'Success':<8}")
        print("-" * 60)
        
        for result in self.results:
            print(f"{result.test_name:<30} {result.avg_time:.3f}s     {result.operations_per_second:>6.1f}     {result.success_rate:>5.1%}")
        
        # Overall statistics
        total_operations = sum(r.operations_count for r in self.results)
        total_time = sum(r.total_time for r in self.results)
        avg_ops_per_sec = total_operations / total_time if total_time > 0 else 0
        avg_success_rate = statistics.mean(r.success_rate for r in self.results) if self.results else 0
        
        print("-" * 60)
        print(f"{'OVERALL':<30} {'-':<12} {avg_ops_per_sec:>6.1f}     {avg_success_rate:>5.1%}")
        
        # Performance assessment
        print(f"\n🎯 Performance Assessment:")
        if avg_ops_per_sec >= 50:
            print("🟢 Excellent performance (≥50 ops/sec)")
        elif avg_ops_per_sec >= 20:
            print("🟡 Good performance (≥20 ops/sec)")
        elif avg_ops_per_sec >= 10:
            print("🟠 Acceptable performance (≥10 ops/sec)")
        else:
            print("🔴 Performance needs improvement (<10 ops/sec)")
        
        if avg_success_rate >= 0.95:
            print("🟢 Excellent reliability (≥95% success)")
        elif avg_success_rate >= 0.90:
            print("🟡 Good reliability (≥90% success)")
        else:
            print("🔴 Reliability issues (<90% success)")
    
    async def run_all_benchmarks(self):
        """Run complete benchmark suite."""
        print("🚀 Starting MCP Performance Benchmarks")
        print("=" * 50)
        
        # Configuration
        config = MCPServerConfig(
            name="benchmark_server",
            endpoint="http://localhost:8000/mcp",
            timeout=30
        )
        
        try:
            async with MCPClient(config) as client:
                print("✅ Connected to MCP server")
                
                # Run benchmarks
                benchmarks = [
                    ("Tool Discovery", self.benchmark_tool_discovery(client, 15)),
                    ("Synchronous Calls", self.benchmark_synchronous_calls(client, 30)),
                    ("Streaming Calls", self.benchmark_streaming_calls(client, 20)),
                    ("Concurrent Calls", self.benchmark_concurrent_calls(client, 5, 10)),
                    ("Mixed Workload", self.benchmark_mixed_workload(client, 15))
                ]
                
                for name, benchmark_coro in benchmarks:
                    print(f"\n🎯 Running {name}...")
                    result = await benchmark_coro
                    self.results.append(result)
                    self.print_result(result)
                
                # Print summary
                self.print_summary()
                
                return True
                
        except MCPConnectionError as e:
            print(f"❌ Failed to connect to MCP server: {e}")
            print("💡 Make sure the test server is running: python test_mcp_server.py")
            return False
        except Exception as e:
            print(f"❌ Benchmark failed: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Main benchmark execution."""
    benchmark = MCPPerformanceBenchmark()
    success = await benchmark.run_all_benchmarks()
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Benchmark crashed: {e}")
        sys.exit(1)