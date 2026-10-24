
# 🤝 Contributing to Pipeline Automation Hub

Thank you for your interest in contributing to the Pipeline Automation Hub! This document provides guidelines and information for contributors.

## 📋 Table of Contents
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Document Processing](#document-processing)
- [Code Standards](#code-standards)
- [Submitting Changes](#submitting-changes)
- [Issue Reporting](#issue-reporting)

## 🚀 Getting Started

### Prerequisites
- **Node.js** 18.x or later
- **Python** 3.11 or later  
- **Yarn** package manager
- **Git** for version control

### Repository Structure
```
pipeline-automation-hub/
├── app/                          # Next.js application
│   ├── components/              # React components
│   ├── api/                     # API routes
│   └── public/outputs/          # Processed document outputs
├── scripts/                     # Python processing engines
├── .github/workflows/           # CI/CD automation
└── README.md                    # Project documentation
```

## 🛠️ Development Setup

### 1. Clone and Install
```bash
git clone https://github.com/GBOGEB/pipeline-automation-hub.git
cd pipeline-automation-hub

# Install Next.js dependencies
cd app
yarn install

# Install Python dependencies  
cd ../scripts
pip install -r requirements.txt  # if available
```

### 2. Environment Setup
```bash
# Copy environment template
cp app/.env.example app/.env.local

# Configure your local environment variables
# Add database connections, API keys, etc.
```

### 3. Start Development Servers
```bash
# Next.js development server
cd app
yarn dev

# Document processing (separate terminal)
cd scripts  
python run_processing.py
```

## 📄 Document Processing

### Processing Pipeline
Our document processing system handles PowerPoint files through multiple stages:

1. **PPT Engine** → Metadata extraction and content analysis
2. **PDF Engine** → Document conversion and processing  
3. **Markdown Engine** → Digital twin generation
4. **Recursive Build** → Cross-linked ecosystem creation

### Adding New File Formats
To support additional document formats:

1. Create a new processor in `scripts/`
2. Follow the existing pattern from `ppt_processor.py`
3. Add metadata extraction logic
4. Update the main processing pipeline
5. Add tests and documentation

### Metadata Schema
Ensure new processors follow the metadata schema:
```json
{
  "original_filename": "string",
  "category": "SYSTEM_ARCHITECTURE | COMPLIANCE | etc.",
  "priority": "CRITICAL | HIGH | MEDIUM | LOW",
  "processing_timestamp": "ISO 8601 timestamp",
  "file_hash": "SHA256 hash",
  "cross_references": ["SCK CEN/XXXX", ...]
}
```

## 🎨 Code Standards

### TypeScript/JavaScript
- Use **TypeScript** for all new code
- Follow **ESLint** configuration in `app/.eslintrc.js`
- Use **Prettier** for code formatting
- Prefer **functional components** with hooks

### Python
- Follow **PEP 8** style guidelines
- Use **type hints** for function signatures
- Include **docstrings** for all classes and functions
- Use **Black** for code formatting

### Commit Messages
Use conventional commit format:
```
feat: add new document processing engine
fix: resolve authentication issue
docs: update API documentation
style: format code with prettier
refactor: restructure component hierarchy
test: add integration tests for PPT processor
```

## 🔄 Submitting Changes

### Pull Request Process
1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'feat: add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### PR Requirements
- ✅ All tests pass
- ✅ Code follows style guidelines
- ✅ Documentation updated (if needed)
- ✅ No merge conflicts
- ✅ Descriptive PR title and description

### Review Process
- Code review by maintainers
- Automated CI/CD checks
- Document processing validation
- Manual testing if needed

## 🐛 Issue Reporting

### Bug Reports
Include the following information:
- **Environment**: OS, Node.js version, browser
- **Steps to reproduce** the issue
- **Expected behavior** vs actual behavior
- **Screenshots** or error logs
- **Additional context** that might help

### Feature Requests  
Describe:
- **Problem** the feature would solve
- **Proposed solution** or implementation ideas
- **Alternatives** considered
- **Additional context** or use cases

### Document Processing Issues
For processing-related issues, include:
- **File type** and size
- **Processing stage** where issue occurs
- **Error messages** from logs
- **Sample files** (if possible and safe to share)

## 🏗️ Architecture Guidelines

### Component Structure
```typescript
// Follow this pattern for new components
interface ComponentProps {
  // Define props with TypeScript
}

export function Component({ prop }: ComponentProps) {
  // Use hooks for state management
  // Keep components focused and single-purpose
  // Include proper error handling
  
  return (
    // JSX with proper accessibility
  );
}
```

### API Routes
```typescript
// app/api/example/route.ts
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    // Handle request logic
    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

### Processing Scripts
```python
# scripts/new_processor.py
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

class NewProcessor:
    """Process documents of a specific type."""
    
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
    
    def process_file(self, filename: str) -> Dict[str, Any]:
        """Process a single file and return results."""
        # Implementation here
        pass
```

## 📚 Documentation

### Code Documentation
- Add **JSDoc** comments for TypeScript functions
- Include **Python docstrings** for all classes/methods
- Document **API endpoints** with request/response examples
- Update **README.md** for significant changes

### Testing
- Write **unit tests** for new functions
- Add **integration tests** for API endpoints
- Include **processing tests** for document engines
- Ensure **CI/CD pipeline** passes

## 🎯 Development Workflow

### Local Development
1. Make changes in feature branch
2. Test locally with `yarn dev` and `python run_processing.py`
3. Run linting: `yarn lint` and `black scripts/`
4. Run tests: `yarn test` (when available)
5. Commit and push changes

### CI/CD Pipeline  
Our automated pipeline:
- ✅ **Code quality** checks (ESLint, Black, TypeScript)
- ✅ **Security** auditing 
- ✅ **Document processing** validation
- ✅ **Build** testing (Next.js production build)
- ✅ **Automated** releases for master branch

## 🤝 Community

### Getting Help
- 💬 **GitHub Discussions** for questions and ideas
- 🐛 **GitHub Issues** for bug reports and feature requests
- 📧 **Email** maintainers for security issues

### Recognition
Contributors will be recognized in:
- 📜 **CONTRIBUTORS.md** file
- 🎉 **Release notes** for significant contributions
- 👥 **GitHub contributors** section

## 📄 License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0 (see [LICENSE](LICENSE), section 5). Third-party attributions are kept in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

Thank you for contributing to Pipeline Automation Hub! 🚀

*For questions about this guide, please open an issue or start a discussion.*
