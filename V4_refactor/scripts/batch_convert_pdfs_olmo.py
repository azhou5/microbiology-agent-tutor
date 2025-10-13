"""
Batch convert VMR PDFs to Markdown using OlmoOCR.

This script processes all DDX Learners PDF files and converts them to
clean Markdown format using OlmoOCR for optimal text extraction, table
preservation, and formatting.

Usage:
    # Basic usage (local GPU)
    python scripts/batch_convert_pdfs_olmo.py
    
    # With external vLLM server
    python scripts/batch_convert_pdfs_olmo.py --server http://remote-server:8000
    
    # Using DeepInfra API (no GPU needed)
    python scripts/batch_convert_pdfs_olmo.py --use-deepinfra --api-key YOUR_KEY

Requirements:
    # Setup olmOCR conda environment:
    conda create -n olmocr python=3.11
    conda activate olmocr
    pip install olmocr[gpu] --extra-index-url https://download.pytorch.org/whl/cu128
    
    # Or for CPU/API usage only:
    pip install olmocr[bench]
    
    # Requires: GPU with 15GB+ VRAM (for local inference)
    # See: https://github.com/allenai/olmocr
"""

import argparse
import logging
import sys
import subprocess
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import json
import shutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OlmoOCRConverter:
    """
    Batch converter for VMR PDFs using OlmoOCR.
    
    Converts PDFs to Markdown with proper formatting, table extraction,
    and metadata preservation using the olmOCR CLI tool.
    """
    
    def __init__(
        self,
        pdf_directory: Path,
        output_directory: Path,
        workspace_directory: Path,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "allenai/olmOCR-7B-0825-FP8",
        use_deepinfra: bool = False
    ):
        """
        Initialize the converter.
        
        Args:
            pdf_directory: Directory containing PDF files
            output_directory: Directory for final Markdown output
            workspace_directory: Temporary workspace for olmOCR
            server_url: Optional external vLLM server URL
            api_key: Optional API key (for DeepInfra, etc.)
            model: Model to use
            use_deepinfra: Use DeepInfra API endpoint
        """
        self.pdf_directory = pdf_directory
        self.output_directory = output_directory
        self.workspace_directory = workspace_directory
        self.server_url = server_url
        self.api_key = api_key
        self.model = model
        self.use_deepinfra = use_deepinfra
        
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.workspace_directory.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            "total": 0,
            "converted": 0,
            "skipped": 0,
            "failed": 0,
            "errors": []
        }
    
    def build_olmocr_command(self, pdf_paths: List[Path]) -> List[str]:
        """
        Build the olmOCR CLI command.
        
        Args:
            pdf_paths: List of PDF paths to convert
        
        Returns:
            Command as list of strings
        """
        cmd = [
            "python", "-m", "olmocr.pipeline",
            str(self.workspace_directory),
            "--markdown",
            "--pdfs"
        ]
        
        # Add PDF paths
        cmd.extend([str(p) for p in pdf_paths])
        
        # Add model
        cmd.extend(["--model", self.model])
        
        # Add server configuration
        if self.use_deepinfra:
            cmd.extend([
                "--server", "https://api.deepinfra.com/v1/openai",
                "--api_key", self.api_key or "",
                "--model", "allenai/olmOCR-7B-0825",
                "--pages_per_group", "50"  # Lower for API rate limits
            ])
        elif self.server_url:
            cmd.extend(["--server", self.server_url])
        
        return cmd
    
    def check_olmocr_installed(self) -> bool:
        """Check if olmOCR is installed."""
        try:
            result = subprocess.run(
                ["python", "-m", "olmocr.pipeline", "--help"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def convert_batch(self, batch_size: int = 50) -> dict:
        """
        Convert all PDFs using olmOCR CLI in batches.
        
        Args:
            batch_size: Number of PDFs to process in each batch
        
        Returns:
            Statistics dictionary
        """
        # Find all PDF files
        pdf_files = list(self.pdf_directory.glob("Episode_*.pdf"))
        self.stats["total"] = len(pdf_files)
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        logger.info(f"PDF directory: {self.pdf_directory}")
        logger.info(f"Workspace: {self.workspace_directory}")
        logger.info(f"Output directory: {self.output_directory}")
        
        if not pdf_files:
            logger.warning("No PDF files found matching pattern 'Episode_*.pdf'")
            return self.stats
        
        # Check already converted
        already_converted = []
        for pdf_file in pdf_files:
            md_file = self.output_directory / f"{pdf_file.stem}.md"
            if md_file.exists():
                already_converted.append(pdf_file)
        
        if already_converted:
            logger.info(f"⏭️  {len(already_converted)} files already converted (skipping)")
            self.stats["skipped"] = len(already_converted)
            pdf_files = [p for p in pdf_files if p not in already_converted]
        
        if not pdf_files:
            logger.info("✅ All files already converted!")
            return self.stats
        
        # Process in batches
        for i in range(0, len(pdf_files), batch_size):
            batch = pdf_files[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(pdf_files) + batch_size - 1) // batch_size
            
            logger.info(f"\n{'='*80}")
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
            logger.info(f"{'='*80}")
            
            # Build olmOCR command
            cmd = self.build_olmocr_command(batch)
            
            logger.info(f"Running: {' '.join(cmd[:10])}... (+ {len(batch)} PDF paths)")
            
            try:
                # Run olmOCR
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600  # 1 hour timeout per batch
                )
                
                if result.returncode == 0:
                    logger.info(f"✅ Batch {batch_num} completed successfully")
                    
                    # Move markdown files to output directory
                    workspace_markdown = self.workspace_directory / "markdown"
                    if workspace_markdown.exists():
                        for md_file in workspace_markdown.glob("*.md"):
                            dest = self.output_directory / md_file.name
                            shutil.copy2(md_file, dest)
                            logger.info(f"  📄 Saved: {md_file.name}")
                    
                    self.stats["converted"] += len(batch)
                else:
                    logger.error(f"❌ Batch {batch_num} failed with code {result.returncode}")
                    logger.error(f"STDOUT: {result.stdout[-500:]}")  # Last 500 chars
                    logger.error(f"STDERR: {result.stderr[-500:]}")
                    self.stats["failed"] += len(batch)
                    self.stats["errors"].append({
                        "batch": batch_num,
                        "files": [p.name for p in batch],
                        "error": result.stderr[-500:]
                    })
                
            except subprocess.TimeoutExpired:
                logger.error(f"❌ Batch {batch_num} timed out after 1 hour")
                self.stats["failed"] += len(batch)
                self.stats["errors"].append({
                    "batch": batch_num,
                    "files": [p.name for p in batch],
                    "error": "Timeout after 1 hour"
                })
            
            except Exception as e:
                logger.error(f"❌ Unexpected error in batch {batch_num}: {e}")
                self.stats["failed"] += len(batch)
                self.stats["errors"].append({
                    "batch": batch_num,
                    "files": [p.name for p in batch],
                    "error": str(e)
                })
        
        # Save conversion report
        report_path = self.output_directory / f"conversion_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report = {
            "stats": self.stats,
            "timestamp": datetime.now().isoformat(),
            "model": self.model,
            "server_url": self.server_url,
            "use_deepinfra": self.use_deepinfra
        }
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        
        logger.info("\n" + "="*80)
        logger.info("CONVERSION COMPLETE")
        logger.info("="*80)
        logger.info(f"Total files: {self.stats['total']}")
        logger.info(f"✅ Converted: {self.stats['converted']}")
        logger.info(f"⏭️  Skipped: {self.stats['skipped']}")
        logger.info(f"❌ Failed: {self.stats['failed']}")
        logger.info(f"Report saved: {report_path}")
        
        return self.stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch convert VMR PDFs to Markdown using OlmoOCR",
        epilog="""
Examples:
  # Local GPU inference:
  python scripts/batch_convert_pdfs_olmo.py
  
  # With external vLLM server:
  python scripts/batch_convert_pdfs_olmo.py --server http://192.168.1.100:8000
  
  # Using DeepInfra API (no GPU):
  export DEEPINFRA_API_KEY="your-key"
  python scripts/batch_convert_pdfs_olmo.py --use-deepinfra --api-key $DEEPINFRA_API_KEY
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--pdf-dir",
        type=str,
        help="Path to PDF directory (default: ../Datasets/vmr_pdfs)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Path to output directory (default: ../Datasets/vmr_markdown)"
    )
    parser.add_argument(
        "--workspace-dir",
        type=str,
        help="Temporary workspace for olmOCR (default: ../Datasets/vmr_olmocr_workspace)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of PDFs per batch (default: 50)"
    )
    parser.add_argument(
        "--server",
        type=str,
        help="External vLLM server URL (e.g., http://server:8000)"
    )
    parser.add_argument(
        "--use-deepinfra",
        action="store_true",
        help="Use DeepInfra API endpoint"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API key (for DeepInfra or other hosted services)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="allenai/olmOCR-7B-0825-FP8",
        help="Model to use (default: allenai/olmOCR-7B-0825-FP8)"
    )
    
    args = parser.parse_args()
    
    # Check olmOCR installation first
    logger.info("Checking olmOCR installation...")
    try:
        result = subprocess.run(
            ["python", "-m", "olmocr.pipeline", "--help"],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            logger.error("olmOCR not installed or not working!")
            logger.error("Please install: pip install olmocr[gpu] --extra-index-url https://download.pytorch.org/whl/cu128")
            logger.error("See: https://github.com/allenai/olmocr")
            return 1
        logger.info("✅ olmOCR is installed")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.error("olmOCR not found!")
        logger.error("Please install: pip install olmocr[gpu]")
        return 1
    
    # Resolve paths
    script_dir = Path(__file__).parent.parent
    microbio_root = script_dir.parent
    
    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else microbio_root / "Datasets" / "vmr_pdfs"
    output_dir = Path(args.output_dir) if args.output_dir else microbio_root / "Datasets" / "vmr_markdown"
    workspace_dir = Path(args.workspace_dir) if args.workspace_dir else microbio_root / "Datasets" / "vmr_olmocr_workspace"
    
    # Validate PDF directory
    if not pdf_dir.exists():
        logger.error(f"PDF directory not found: {pdf_dir}")
        logger.error("Please provide a valid --pdf-dir path")
        return 1
    
    logger.info("\n" + "🚀"*40)
    logger.info("VMR PDF TO MARKDOWN CONVERSION (olmOCR)")
    logger.info("🚀"*40)
    logger.info(f"📁 PDF directory: {pdf_dir}")
    logger.info(f"📁 Output directory: {output_dir}")
    logger.info(f"📁 Workspace: {workspace_dir}")
    logger.info(f"🤖 Model: {args.model}")
    if args.server:
        logger.info(f"🌐 Server: {args.server}")
    if args.use_deepinfra:
        logger.info("🌐 Using DeepInfra API")
    logger.info("")
    
    # Create converter and run
    converter = OlmoOCRConverter(
        pdf_directory=pdf_dir,
        output_directory=output_dir,
        workspace_directory=workspace_dir,
        server_url=args.server,
        api_key=args.api_key,
        model=args.model,
        use_deepinfra=args.use_deepinfra
    )
    
    stats = converter.convert_batch(batch_size=args.batch_size)
    
    # Exit with error if any failed
    if stats["failed"] > 0:
        logger.warning(f"⚠️  {stats['failed']} files failed to convert")
        return 1
    
    logger.info("\n✅ All conversions completed successfully!")
    logger.info(f"📄 Markdown files saved to: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

