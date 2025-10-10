# -*- coding: utf-8 -*-
"""Real streaming MCP server using progress reporting for actual server-side streaming."""

import asyncio
import time

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

# Create stateful MCP server with real progress reporting
mcp = FastMCP("real-streaming-server")


@mcp.tool()
async def real_time_data_stream(duration: int = 5, ctx: Context[ServerSession, None] = None) -> str:
    """Generate real-time data stream with progress reporting.
    
    This tool demonstrates actual server-side streaming using MCP's
    progress reporting mechanism to send updates as they happen.
    """
    if ctx:
        await ctx.info(f"🚀 Starting real-time data stream for {duration} seconds")
    
    result_lines = []
    start_time = time.time()
    
    for i in range(duration):
        if ctx:
            # Report progress before processing each step
            progress = i / duration
            await ctx.report_progress(
                progress=progress,
                total=1.0,
                message=f"Generating data point {i+1}/{duration}"
            )
        
        # Simulate real-time data generation
        await asyncio.sleep(1)
        current_time = time.time()
        elapsed = current_time - start_time
        
        line = f"[{elapsed:.1f}s] Real-time data point {i+1}/{duration}: {current_time:.2f}"
        result_lines.append(line)
        
        if ctx:
            await ctx.debug(f"Generated: {line}")
    
    # Final progress report
    if ctx:
        await ctx.report_progress(
            progress=1.0,
            total=1.0,
            message=f"Completed {duration} data points"
        )
        await ctx.info("✅ Real-time data stream completed")
    
    return "\n".join(result_lines)


@mcp.tool()
async def progressive_search(query: str, max_results: int = 5, ctx: Context[ServerSession, None] = None) -> str:
    """Simulate progressive search with real-time result discovery and progress reporting."""
    if ctx:
        await ctx.info(f"🔍 Starting progressive search for '{query}'")
    
    results = []
    
    # Initial search start
    results.append(f"🔍 Starting search for '{query}'...")
    if ctx:
        await ctx.report_progress(0.0, 1.0, "Initializing search...")
    
    await asyncio.sleep(0.3)
    
    # Progressive result discovery with progress reporting
    for i in range(max_results):
        progress = i / max_results
        if ctx:
            await ctx.report_progress(
                progress=progress,
                total=1.0,
                message=f"Searching result {i+1}/{max_results}"
            )
        
        await asyncio.sleep(0.8)  # Simulate search time per result
        
        result = f"📄 Result {i+1}: Document about '{query}' (relevance: {95-i*5}%)"
        results.append(result)
        
        if ctx:
            await ctx.debug(f"Found: {result}")
        
        # Add processing indicator
        if i < max_results - 1:
            results.append(f"   ⏳ Searching for more results...")
    
    # Search completion
    await asyncio.sleep(0.2)
    results.append(f"✅ Search completed. Found {max_results} results for '{query}'")
    
    if ctx:
        await ctx.report_progress(1.0, 1.0, "Search completed")
        await ctx.info(f"✅ Found {max_results} results for '{query}'")
    
    return "\n".join(results)


@mcp.tool()
async def long_computation(steps: int = 10, ctx: Context[ServerSession, None] = None) -> str:
    """Simulate long computation with detailed progress updates."""
    if ctx:
        await ctx.info(f"🚀 Starting computation with {steps} steps")
    
    results = []
    results.append(f"🚀 Starting computation with {steps} steps...")
    
    for step in range(1, steps + 1):
        # Report progress before each step - always report regardless of token
        progress = (step - 1) / steps
        if ctx:
            print(f"📊 Reporting progress: {progress:.2f} for step {step}/{steps}")
            await ctx.report_progress(
                progress=progress,
                total=1.0,
                message=f"Computing step {step}/{steps}"
            )
        
        # Variable processing time per step
        processing_time = 0.3 + (step % 3) * 0.2
        await asyncio.sleep(processing_time)
        
        # Simulate computation result
        result_value = step * step + (step % 5)
        progress_pct = (step / steps) * 100
        
        line = f"📊 Step {step}/{steps} ({progress_pct:.1f}%): Computed value = {result_value}"
        results.append(line)
        
        if ctx:
            await ctx.debug(f"Step {step} completed: value = {result_value}")
        
        # Add intermediate status for longer steps
        if step % 3 == 0 and step < steps:
            results.append(f"   🔄 Checkpoint reached. Continuing computation...")
    
    # Final progress
    if ctx:
        print(f"📊 Reporting final progress: 1.0")
        await ctx.report_progress(1.0, 1.0, "Computation completed")
        await ctx.info("🎉 Computation completed successfully!")
    
    results.append(f"🎉 Computation completed successfully!")
    return "\n".join(results)


@mcp.tool()
async def simulated_file_processing(file_count: int = 3, ctx: Context[ServerSession, None] = None) -> str:
    """Simulate processing multiple files with progress reporting."""
    if ctx:
        await ctx.info(f"📁 Starting batch processing of {file_count} files")
    
    results = []
    files = [f"document_{i+1}.txt" for i in range(file_count)]
    
    results.append(f"📁 Starting batch processing of {file_count} files...")
    
    for i, filename in enumerate(files):
        # Report progress for each file
        progress = i / file_count
        if ctx:
            await ctx.report_progress(
                progress=progress,
                total=1.0,
                message=f"Processing {filename} ({i+1}/{file_count})"
            )
        
        # Simulate file size variation affecting processing time
        file_size = (i + 1) * 100 + (i % 2) * 50  # KB
        processing_time = file_size / 200  # Simulate processing speed
        
        results.append(f"🔄 Processing {filename} ({file_size}KB)...")
        if ctx:
            await ctx.debug(f"Processing {filename} ({file_size}KB)")
        
        await asyncio.sleep(processing_time)
        
        # Processing result
        words_found = (i + 1) * 245 + (i % 3) * 67
        results.append(f"✅ {filename}: Processed {words_found} words in {processing_time:.1f}s")
        
        if ctx:
            await ctx.debug(f"Completed {filename}: {words_found} words")
        
        # Add separator except for last file
        if i < len(files) - 1:
            results.append("---")
    
    # Final progress
    total_time = sum((i + 1) * 100 + (i % 2) * 50 for i in range(file_count)) / 200
    results.append(f"🏁 Batch processing completed in {total_time:.1f}s")
    
    if ctx:
        await ctx.report_progress(1.0, 1.0, "Batch processing completed")
        await ctx.info(f"🏁 Processed {file_count} files in {total_time:.1f}s")
    
    return "\n".join(results)


if __name__ == "__main__":
    print("🌊 Starting Real Streaming MCP Server with Progress Reporting...")
    print("📡 This server uses MCP's progress reporting for true streaming")
    print("🔗 Server will be available at: http://localhost:8002/mcp")
    print("📋 Available tools (with progress reporting):")
    print("  - real_time_data_stream: Generate real-time data with progress")
    print("  - progressive_search: Search with progress updates")
    print("  - long_computation: Long computation with step-by-step progress")
    print("  - simulated_file_processing: File processing with progress")
    
    # Configure server settings
    mcp.settings.host = "localhost"
    mcp.settings.port = 8002
    
    # Run with streamable HTTP (supports progress reporting)
    mcp.run(transport="streamable-http")