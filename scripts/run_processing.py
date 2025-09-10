
#!/usr/bin/env python3
"""
Run the complete document processing pipeline
"""

import sys
import os
from pathlib import Path
import subprocess
import json

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

def run_ppt_processing():
    """Execute PowerPoint processing"""
    print("🔄 Phase 1: PowerPoint Processing Engine")
    print("-" * 50)
    
    try:
        # Run the PPT processor
        result = subprocess.run([
            sys.executable, 
            str(current_dir / "ppt_processor.py")
        ], capture_output=True, text=True, cwd=current_dir)
        
        if result.returncode == 0:
            print("✅ PPT Processing completed successfully!")
            print(result.stdout)
        else:
            print("❌ PPT Processing failed!")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error running PPT processor: {e}")
        return False
    
    return True

def generate_summary_report():
    """Generate processing summary report"""
    print("\n📊 Generating Summary Report")
    print("-" * 50)
    
    try:
        summary_path = Path("/home/ubuntu/pipeline_automation_app/app/public/outputs/processing_summary.json")
        
        if summary_path.exists():
            with open(summary_path, 'r') as f:
                summary = json.load(f)
            
            print(f"📁 Total Files Processed: {summary.get('total_files', 0)}")
            print(f"✅ Successful: {summary.get('successful', 0)}")
            print(f"❌ Failed: {summary.get('failed', 0)}")
            
            print("\n📂 Categories Found:")
            for category, count in summary.get('categories_summary', {}).items():
                print(f"  • {category}: {count} files")
            
            print(f"\n🔗 Cross-references Extracted: {len(summary.get('cross_references_global', []))}")
            for ref in summary.get('cross_references_global', []):
                print(f"  • {ref}")
            
            return True
        else:
            print("⚠️  Summary file not found")
            return False
            
    except Exception as e:
        print(f"❌ Error generating summary: {e}")
        return False

def main():
    """Main processing pipeline"""
    print("🎯 Pipeline Automation Hub - Document Processing Pipeline")
    print("=" * 60)
    
    # Phase 1: PPT Processing
    if not run_ppt_processing():
        print("❌ Pipeline failed at PPT processing stage")
        sys.exit(1)
    
    # Generate Summary
    if not generate_summary_report():
        print("⚠️  Warning: Could not generate summary report")
    
    print("\n🎉 Document Processing Pipeline Completed Successfully!")
    print("=" * 60)
    
    # Show output locations
    output_base = "/home/ubuntu/pipeline_automation_app/app/public/outputs"
    print(f"📁 Digital Twins: {output_base}/digital_twins/")
    print(f"📊 Metadata: {output_base}/metadata/")
    print(f"🔗 Cross-references: {output_base}/cross_references/")
    print(f"📋 Summary: {output_base}/processing_summary.json")

if __name__ == "__main__":
    main()
