
---
name: 📄 Document Processing Issue
about: Report issues with PPT, PDF, or Markdown processing engines
title: '[PROCESSING] '
labels: 'processing, bug'
assignees: ''
---

## 📄 Processing Issue Summary
Brief description of the document processing problem.

## 🔄 Processing Stage
Where in the pipeline does the issue occur?
- [ ] **PPT Engine** - PowerPoint file processing
- [ ] **PDF Engine** - PDF conversion/processing
- [ ] **Markdown Engine** - Digital twin generation
- [ ] **Metadata Extraction** - File analysis and categorization
- [ ] **Cross-Reference System** - SCK CEN reference mapping
- [ ] **Recursive Build** - Navigation system generation
- [ ] **File Upload/Storage** - File handling and storage

## 📁 File Information
- **File Type**: .pptx / .pdf / .docx / other
- **File Size**: e.g., 15MB
- **File Count**: Single file / Multiple files (specify number)
- **Source**: Upload / Master Input / External

## 🎯 Expected Processing Output
What should the processing pipeline produce?
- [ ] Digital twin (.md file)
- [ ] Metadata JSON
- [ ] Cross-references extracted
- [ ] Category classification
- [ ] Visual artifacts processed
- [ ] Other: ___________

## ❌ Actual Processing Result
What actually happened during processing?
- [ ] Processing failed completely
- [ ] Partial processing completed
- [ ] Incorrect metadata extracted
- [ ] Missing cross-references
- [ ] Wrong file categorization
- [ ] Corrupted output files
- [ ] Other: ___________

## 📝 Error Messages
```
Paste any error messages from processing logs here
```

## 🔍 Processing Logs
```
Include relevant logs from:
- Python processing scripts
- API endpoint responses
- Browser console errors
- System logs
```

## 📊 Processing Statistics
If available, include:
- **Processing Time**: How long did it take?
- **Memory Usage**: Any memory issues?
- **CPU Usage**: High resource consumption?
- **File Output Size**: Size of generated files

## 🧪 Reproducibility
- [ ] Issue occurs consistently with the same file
- [ ] Issue occurs with multiple similar files
- [ ] Issue is intermittent/random
- [ ] Issue only occurs in specific conditions

## 🌐 Environment Details
- **Processing Location**: Local development / Production / CI/CD
- **Python Version**: e.g., 3.11.0
- **Node.js Version**: e.g., 18.17.0
- **Operating System**: e.g., Ubuntu 20.04
- **Available RAM**: e.g., 8GB
- **Available Disk Space**: e.g., 50GB free

## 🔗 Sample Files
If possible and safe to share:
- [ ] Can provide sample file that reproduces the issue
- [ ] File contains sensitive data (cannot share)
- [ ] Similar public file available (provide link)

## 📋 Processing Configuration
- **Master Input Directory**: Standard / Custom path
- **Output Directory**: Standard / Custom path
- **Processing Batch Size**: Single / Multiple files
- **Custom Processing Parameters**: Any special settings

## 🎯 Processing Categories Affected
Which document categories are impacted?
- [ ] SYSTEM_ARCHITECTURE
- [ ] COMPLIANCE
- [ ] INFRASTRUCTURE  
- [ ] STANDARDS
- [ ] VALUES_POLICY
- [ ] PROJECT_STATUS
- [ ] SYSTEMS
- [ ] GENERAL

## 🔄 Workaround Available
Is there a temporary workaround?
- [ ] Yes - describe below
- [ ] No workaround found
- [ ] Partial workaround available

**Workaround Description:**
```
Describe any temporary solutions that work
```

## 🎯 Business Impact
How does this affect your workflow?
- [ ] Blocks all document processing
- [ ] Affects specific file types only
- [ ] Reduces processing efficiency
- [ ] Causes data quality issues
- [ ] Minor inconvenience
- [ ] Other: ___________

## 🔍 Additional Investigation
Have you tried:
- [ ] Reprocessing the same file
- [ ] Processing similar files
- [ ] Different processing parameters
- [ ] Manual processing steps
- [ ] Alternative file formats

## 📚 Related Documentation
- Link to relevant processing documentation
- Reference to similar resolved issues
- Related feature requests or enhancements

---

### 📋 For Maintainers
- [ ] Processing issue confirmed
- [ ] Root cause identified
- [ ] Processing engine affected determined
- [ ] Fix priority assigned
- [ ] Test cases created
