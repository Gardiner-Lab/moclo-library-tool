/**
 * Part Upload Form JavaScript
 * Handles client-side validation and form submission for both manual and GenBank file uploads
 */

/**
 * Initialize the upload form
 */
function initUploadForm() {
    // Initialize toggle buttons
    initToggleButtons();
    
    // Initialize manual upload form
    initManualUploadForm();
    
    // Initialize GenBank upload form
    initGenbankUploadForm();

    // Initialize Bulk upload form
    initBulkUploadForm();
}

/**
 * Initialize toggle buttons for switching between upload methods
 */
function initToggleButtons() {
    const manualToggle = document.getElementById('manualToggle');
    const genbankToggle = document.getElementById('genbankToggle');
    const bulkToggle = document.getElementById('bulkToggle');
    const manualCard = document.getElementById('manualUploadCard');
    const genbankCard = document.getElementById('genbankUploadCard');
    const bulkCard = document.getElementById('bulkUploadCard');
    
    manualToggle.addEventListener('click', () => {
        manualToggle.classList.add('active');
        genbankToggle.classList.remove('active');
        bulkToggle.classList.remove('active');
        manualCard.style.display = 'block';
        genbankCard.style.display = 'none';
        bulkCard.style.display = 'none';
    });
    
    genbankToggle.addEventListener('click', () => {
        genbankToggle.classList.add('active');
        manualToggle.classList.remove('active');
        bulkToggle.classList.remove('active');
        genbankCard.style.display = 'block';
        manualCard.style.display = 'none';
        bulkCard.style.display = 'none';
    });

    bulkToggle.addEventListener('click', () => {
        bulkToggle.classList.add('active');
        manualToggle.classList.remove('active');
        genbankToggle.classList.remove('active');
        bulkCard.style.display = 'block';
        manualCard.style.display = 'none';
        genbankCard.style.display = 'none';
    });
}

/**
 * Initialize manual upload form
 */
function initManualUploadForm() {
    const form = document.getElementById('uploadForm');
    const submitButton = document.getElementById('submitButton');
    const cancelButton = document.getElementById('cancelButton');
    const sequenceInput = document.getElementById('sequence');
    const overhang5Input = document.getElementById('overhang5prime');
    const overhang3Input = document.getElementById('overhang3prime');

    // Set up event listeners
    form.addEventListener('submit', handleManualSubmit);
    cancelButton.addEventListener('click', handleCancel);

    // Real-time validation for sequence
    sequenceInput.addEventListener('input', handleSequenceInput);
    sequenceInput.addEventListener('blur', () => validateSequence(sequenceInput.value));

    // Real-time validation for overhangs
    overhang5Input.addEventListener('input', handleOverhangInput);
    overhang5Input.addEventListener('blur', () => validateOverhang(overhang5Input.value, 'overhang5prime'));
    
    overhang3Input.addEventListener('input', handleOverhangInput);
    overhang3Input.addEventListener('blur', () => validateOverhang(overhang3Input.value, 'overhang3prime'));

    // Validation for other fields
    document.getElementById('partName').addEventListener('blur', function() {
        validateRequired(this.value, 'partName', 'Part name');
    });

    document.getElementById('partType').addEventListener('blur', function() {
        validateRequired(this.value, 'partType', 'Part type');
    });

    document.getElementById('labSource').addEventListener('blur', function() {
        validateRequired(this.value, 'labSource', 'Lab source');
    });
}

/**
 * Initialize GenBank upload form
 */
function initGenbankUploadForm() {
    const form = document.getElementById('genbankUploadForm');
    const fileInput = document.getElementById('genbankFile');
    const fileUploadArea = document.getElementById('fileUploadArea');
    const fileSelected = document.getElementById('fileSelected');
    const fileName = document.getElementById('fileName');
    const removeFileBtn = document.getElementById('removeFileBtn');
    const submitButton = document.getElementById('genbankSubmitButton');
    const cancelButton = document.getElementById('genbankCancelButton');
    
    // File upload area click
    fileUploadArea.addEventListener('click', () => {
        if (!fileSelected.style.display || fileSelected.style.display === 'none') {
            fileInput.click();
        }
    });
    
    // File input change
    fileInput.addEventListener('change', handleFileSelect);
    
    // Drag and drop
    fileUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileUploadArea.classList.add('drag-over');
    });
    
    fileUploadArea.addEventListener('dragleave', () => {
        fileUploadArea.classList.remove('drag-over');
    });
    
    fileUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        fileUploadArea.classList.remove('drag-over');
        
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelect();
        }
    });
    
    // Remove file button
    removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.value = '';
        fileSelected.style.display = 'none';
        fileUploadArea.querySelector('.file-upload-prompt').style.display = 'block';
        clearError('genbankFileError');
    });
    
    // Form submission
    form.addEventListener('submit', handleGenbankSubmit);
    cancelButton.addEventListener('click', handleCancel);
}

/**
 * Handle file selection
 */
function handleFileSelect() {
    const fileInput = document.getElementById('genbankFile');
    const fileSelected = document.getElementById('fileSelected');
    const fileName = document.getElementById('fileName');
    const fileUploadArea = document.getElementById('fileUploadArea');
    
    if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        
        // Validate file extension
        if (!file.name.toLowerCase().endsWith('.gb') && !file.name.toLowerCase().endsWith('.gbk') && !file.name.toLowerCase().endsWith('.genbank')) {
            showError('genbankFileError', 'Please select a GenBank file (.gb, .gbk, or .genbank)');
            fileInput.value = '';
            return;
        }
        
        // Show selected file
        fileName.textContent = file.name;
        fileUploadArea.querySelector('.file-upload-prompt').style.display = 'none';
        fileSelected.style.display = 'flex';
        clearError('genbankFileError');
    }
}

/**
 * Handle manual form submission
 */
async function handleManualSubmit(event) {
    event.preventDefault();
    
    // Clear previous form-level errors
    clearError('formError');
    
    // Validate form
    if (!validateForm()) {
        showError('formError', 'Please fix the errors above before submitting');
        document.getElementById('formError').classList.add('show');
        return;
    }
    
    // Get form data
    const formData = {
        name: document.getElementById('partName').value.trim(),
        part_type: document.getElementById('partType').value,
        sequence: document.getElementById('sequence').value.replace(/\s/g, '').toUpperCase(),
        overhang_5prime: document.getElementById('overhang5prime').value.replace(/\s/g, '').toUpperCase(),
        overhang_3prime: document.getElementById('overhang3prime').value.replace(/\s/g, '').toUpperCase(),
        lab_source: document.getElementById('labSource').value.trim(),
        description: document.getElementById('description').value.trim() || undefined
    };
    
    // Set loading state
    const submitButton = document.getElementById('submitButton');
    const originalText = submitButton.textContent;
    setButtonLoading(submitButton, true);
    submitButton.textContent = 'Uploading...';
    
    try {
        // Submit to API
        const response = await apiRequest('/api/parts', {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        // Success - show message and redirect
        showFlashMessage('Part uploaded successfully!', 'success');
        
        // Redirect to parts browser after a short delay
        setTimeout(() => {
            window.location.href = '/parts';
        }, 1000);
        
    } catch (error) {
        // Handle errors
        setButtonLoading(submitButton, false);
        submitButton.textContent = originalText;
        
        let errorMessage = error.message || 'Failed to upload part';
        
        // Display error
        showError('formError', errorMessage);
        document.getElementById('formError').classList.add('show');
        
        // Scroll to error
        document.getElementById('formError').scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
        });
    }
}

/**
 * Handle GenBank form submission
 */
async function handleGenbankSubmit(event) {
    event.preventDefault();
    
    // Clear previous errors
    clearError('genbankFormError');
    clearError('genbankFileError');
    
    // Validate file is selected
    const fileInput = document.getElementById('genbankFile');
    if (!fileInput.files || fileInput.files.length === 0) {
        showError('genbankFileError', 'Please select a GenBank file');
        return;
    }
    
    // Create FormData
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    // Add optional fields if provided
    const labSource = document.getElementById('genbankLabSource').value.trim();
    if (labSource) {
        formData.append('lab_source', labSource);
    }
    
    const partType = document.getElementById('genbankPartType').value;
    if (partType) {
        formData.append('part_type', partType);
    }

    const genbankLevel = document.getElementById('genbankLevel') ? document.getElementById('genbankLevel').value : '';
    const asBackbone = genbankLevel === 'backbone';
    if (genbankLevel && !asBackbone) {
        formData.append('level', genbankLevel);
    }
    const endpoint = asBackbone ? '/api/backbones' : '/api/parts';
    
    // Set loading state
    const submitButton = document.getElementById('genbankSubmitButton');
    const originalText = submitButton.textContent;
    setButtonLoading(submitButton, true);
    submitButton.textContent = 'Processing...';
    
    try {
        // Submit to API (multipart/form-data)
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin'
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || errorData.message || 'Upload failed');
        }

        const data = await response.json();

        // Success - show message with details
        let message = asBackbone
            ? 'Backbone uploaded successfully from GenBank file!'
            : 'Part uploaded successfully from GenBank file!';
        if (!asBackbone && data.detected_type) {
            message += ` (Detected type: ${data.detected_type})`;
        }
        showFlashMessage(message, 'success');

        // Redirect to the relevant browser after a short delay
        setTimeout(() => {
            window.location.href = asBackbone ? '/backbones' : '/parts';
        }, 1500);
        
    } catch (error) {
        // Handle errors
        setButtonLoading(submitButton, false);
        submitButton.textContent = originalText;
        
        let errorMessage = error.message || 'Failed to upload GenBank file';
        
        // Display error
        showError('genbankFormError', errorMessage);
        document.getElementById('genbankFormError').classList.add('show');
        
        // Scroll to error
        document.getElementById('genbankFormError').scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
        });
    }
}

/**
 * Handle sequence input - convert to uppercase and filter invalid characters
 */
function handleSequenceInput(event) {
    const input = event.target;
    const cursorPosition = input.selectionStart;
    const originalLength = input.value.length;
    
    // Remove whitespace and convert to uppercase
    let cleaned = input.value.replace(/\s/g, '').toUpperCase();
    
    // Filter out invalid characters
    cleaned = cleaned.replace(/[^ATCG]/g, '');
    
    input.value = cleaned;
    
    // Adjust cursor position
    const lengthDiff = originalLength - cleaned.length;
    input.setSelectionRange(cursorPosition - lengthDiff, cursorPosition - lengthDiff);
    
    // Update sequence info
    updateSequenceInfo(cleaned);
    
    // Clear error if user is typing
    if (cleaned.length > 0) {
        clearError('sequenceError');
    }
}

/**
 * Handle overhang input - convert to uppercase and filter invalid characters
 */
function handleOverhangInput(event) {
    const input = event.target;
    const cursorPosition = input.selectionStart;
    const originalLength = input.value.length;
    
    // Remove whitespace and convert to uppercase
    let cleaned = input.value.replace(/\s/g, '').toUpperCase();
    
    // Filter out invalid characters and limit to 4 characters
    cleaned = cleaned.replace(/[^ATCG]/g, '').substring(0, 4);
    
    input.value = cleaned;
    
    // Adjust cursor position
    const lengthDiff = originalLength - cleaned.length;
    input.setSelectionRange(cursorPosition - lengthDiff, cursorPosition - lengthDiff);
    
    // Clear error if user is typing
    if (cleaned.length > 0) {
        clearError(input.id + 'Error');
    }
}

/**
 * Update sequence information display
 */
function updateSequenceInfo(sequence) {
    const infoElement = document.getElementById('sequenceInfo');
    
    if (sequence.length === 0) {
        infoElement.classList.remove('show');
        return;
    }
    
    const length = sequence.length;
    const gcCount = (sequence.match(/[GC]/g) || []).length;
    const gcContent = length > 0 ? ((gcCount / length) * 100).toFixed(1) : 0;
    
    infoElement.innerHTML = `
        <strong>Sequence Info:</strong> 
        Length: ${length} bp | 
        GC Content: ${gcContent}%
    `;
    infoElement.classList.add('show');
}

/**
 * Validate required field
 */
function validateRequired(value, fieldId, fieldName) {
    const errorId = fieldId + 'Error';
    
    if (!value || value.trim() === '') {
        showError(errorId, `${fieldName} is required`);
        return false;
    }
    
    clearError(errorId);
    return true;
}

/**
 * Validate DNA sequence
 */
function validateSequence(sequence) {
    const errorId = 'sequenceError';
    
    // Check if empty
    if (!sequence || sequence.trim() === '') {
        showError(errorId, 'DNA sequence is required');
        return false;
    }
    
    // Remove whitespace
    const cleaned = sequence.replace(/\s/g, '').toUpperCase();
    
    // Check minimum length
    if (cleaned.length < 8) {
        showError(errorId, 'Sequence must be at least 8 bases long');
        return false;
    }
    
    // Check for invalid characters
    if (!/^[ATCG]+$/.test(cleaned)) {
        showError(errorId, 'Sequence must contain only A, T, C, G characters');
        return false;
    }
    
    clearError(errorId);
    return true;
}

/**
 * Validate overhang sequence
 */
function validateOverhang(overhang, fieldId) {
    const errorId = fieldId + 'Error';
    const fieldName = fieldId === 'overhang5prime' ? "5' overhang" : "3' overhang";
    
    // Check if empty
    if (!overhang || overhang.trim() === '') {
        showError(errorId, `${fieldName} is required`);
        return false;
    }
    
    // Remove whitespace
    const cleaned = overhang.replace(/\s/g, '').toUpperCase();
    
    // Check length
    if (cleaned.length !== 4) {
        showError(errorId, `${fieldName} must be exactly 4 bases`);
        return false;
    }
    
    // Check for invalid characters
    if (!/^[ATCG]{4}$/.test(cleaned)) {
        showError(errorId, `${fieldName} must contain only A, T, C, G characters`);
        return false;
    }
    
    clearError(errorId);
    return true;
}

/**
 * Validate entire form
 */
function validateForm() {
    const partName = document.getElementById('partName').value;
    const partType = document.getElementById('partType').value;
    const sequence = document.getElementById('sequence').value;
    const overhang5 = document.getElementById('overhang5prime').value;
    const overhang3 = document.getElementById('overhang3prime').value;
    const labSource = document.getElementById('labSource').value;
    
    let isValid = true;
    
    // Validate all fields
    isValid = validateRequired(partName, 'partName', 'Part name') && isValid;
    isValid = validateRequired(partType, 'partType', 'Part type') && isValid;
    isValid = validateSequence(sequence) && isValid;
    isValid = validateOverhang(overhang5, 'overhang5prime') && isValid;
    isValid = validateOverhang(overhang3, 'overhang3prime') && isValid;
    isValid = validateRequired(labSource, 'labSource', 'Lab source') && isValid;
    
    return isValid;
}

/**
 * Handle cancel button
 */
function handleCancel() {
    if (confirm('Are you sure you want to cancel? Any unsaved changes will be lost.')) {
        window.location.href = '/parts';
    }
}

/**
 * Show error message
 */
function showError(elementId, message) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        
        // Add error class to associated input
        const inputId = elementId.replace('Error', '');
        const inputElement = document.getElementById(inputId);
        if (inputElement) {
            inputElement.classList.add('error');
        }
    }
}

/**
 * Clear error message
 */
function clearError(elementId) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.textContent = '';
        errorElement.style.display = 'none';
        
        // Remove error class from associated input
        const inputId = elementId.replace('Error', '');
        const inputElement = document.getElementById(inputId);
        if (inputElement) {
            inputElement.classList.remove('error');
        }
    }
}

// Export for use in other modules
window.initUploadForm = initUploadForm;


/**
 * Initialize Bulk Upload form
 */
function initBulkUploadForm() {
    const form = document.getElementById('bulkUploadForm');
    const fileInput = document.getElementById('bulkFiles');
    const fileUploadArea = document.getElementById('bulkFileUploadArea');
    const filePrompt = document.getElementById('bulkFilePrompt');
    const fileList = document.getElementById('bulkFileList');
    const fileCount = document.getElementById('bulkFileCount');
    const clearBtn = document.getElementById('bulkClearBtn');

    // Click to select files
    fileUploadArea.addEventListener('click', () => {
        if (fileList.style.display === 'none' || !fileList.style.display) {
            fileInput.click();
        }
    });

    // File input change
    fileInput.addEventListener('change', () => {
        updateBulkFileDisplay();
    });

    // Drag and drop
    fileUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileUploadArea.classList.add('drag-over');
    });

    fileUploadArea.addEventListener('dragleave', () => {
        fileUploadArea.classList.remove('drag-over');
    });

    fileUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        fileUploadArea.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            updateBulkFileDisplay();
        }
    });

    // Clear button
    clearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.value = '';
        fileList.style.display = 'none';
        filePrompt.style.display = 'block';
        const levelGroup = document.getElementById('bulkLevelGroup');
        const rows = document.getElementById('bulkFileRows');
        if (levelGroup) levelGroup.style.display = 'none';
        if (rows) rows.innerHTML = '';
    });

    // "Set all to" batch buttons for category and part type
    const levelGroup = document.getElementById('bulkLevelGroup');
    if (levelGroup) {
        levelGroup.querySelectorAll('[data-setall]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const val = btn.getAttribute('data-setall');
                document.querySelectorAll('#bulkFileRows .bulk-file-level').forEach((sel) => {
                    sel.value = val;
                    sel.dispatchEvent(new Event('change'));
                });
            });
        });
        levelGroup.querySelectorAll('[data-settype]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const val = btn.getAttribute('data-settype');
                document.querySelectorAll('#bulkFileRows .bulk-file-parttype').forEach((sel) => {
                    sel.value = val;
                });
            });
        });
    }

    // Form submission
    form.addEventListener('submit', handleBulkSubmit);
}

/**
 * Guess a MoClo level from a filename. Looks for an L / Lvl / Level token
 * next to a 0, 1 or 2 with a separator on both sides so it does not match
 * digits inside an unrelated id. Returns '', '0', '1' or '2'.
 */
function inferMocloLevel(filename) {
    const m = String(filename).match(/(?:^|[_\-.\s])l(?:vl|evel)?[_\-.\s]*([012])(?:[_\-.\s]|$)/i);
    return m ? m[1] : '';
}

/**
 * Guess a part type from a filename. Only fires on a whole word so it does not
 * mislabel cryptic plasmid ids. Returns a Part.VALID_PART_TYPES value or ''.
 */
function inferPartType(filename) {
    const s = String(filename).toLowerCase();
    if (/cassette/.test(s)) return 'ExpressionCassette';
    if (/promoter/.test(s)) return 'NonCodingPromoter';
    if (/terminator/.test(s)) return 'NonCodingTerminator';
    if (/(^|[^a-z])(cds|coding)([^a-z]|$)/.test(s)) return 'Coding';
    if (/intron/.test(s)) return 'NonCodingIntron';
    if (/(^|[^a-z])(utr|5utr|3utr)([^a-z]|$)/.test(s)) return 'NonCodingOther';
    return '';
}

/**
 * Part-type <option> list for a given category. Level 0 offers the basic part
 * types; a Level 1 or Level 2 file is a transcription unit, so it offers only
 * "expression cassette" or "non-coding other".
 */
function partTypeOptionsHtml(levelValue) {
    if (levelValue === '1' || levelValue === '2') {
        return '<option value="">Type: auto</option>' +
            '<option value="ExpressionCassette">Expression cassette</option>' +
            '<option value="NonCodingOther">Non-coding other</option>';
    }
    return '<option value="">Type: auto</option>' +
        '<option value="Coding">Coding</option>' +
        '<option value="NonCodingPromoter">Promoter</option>' +
        '<option value="NonCodingTerminator">Terminator</option>' +
        '<option value="NonCodingIntron">Intron</option>' +
        '<option value="NonCodingOther">Other</option>';
}

/**
 * Return the filename with an `_L<level>` token, replacing any conflicting
 * level token already present. No change when level is '' or the name already
 * carries the right token.
 */
function nameWithLevel(filename, level) {
    if (!/^[012]$/.test(level)) return filename;
    if (inferMocloLevel(filename) === level) return filename;
    const dot = filename.lastIndexOf('.');
    let base = dot > 0 ? filename.slice(0, dot) : filename;
    const ext = dot > 0 ? filename.slice(dot) : '';
    const tokenRe = /(^|[_\-.\s])l(?:vl|evel)?[_\-.\s]*[012](?=[_\-.\s]|$)/i;
    if (tokenRe.test(base)) {
        base = base.replace(tokenRe, `$1L${level}`);
    } else {
        base = `${base}_L${level}`;
    }
    return base + ext;
}

/**
 * Build a File with a new name, falling back to the original if the runtime
 * does not allow constructing File objects.
 */
function renameFile(file, newName) {
    if (newName === file.name) return file;
    try {
        return new File([file], newName, { type: file.type, lastModified: file.lastModified });
    } catch (e) {
        return file;
    }
}

/**
 * Update the file count display for bulk upload
 */
function updateBulkFileDisplay() {
    const fileInput = document.getElementById('bulkFiles');
    const filePrompt = document.getElementById('bulkFilePrompt');
    const fileList = document.getElementById('bulkFileList');
    const fileCount = document.getElementById('bulkFileCount');

    if (fileInput.files.length > 0) {
        // Validate all files
        const validFiles = [];
        for (let i = 0; i < fileInput.files.length; i++) {
            const name = fileInput.files[i].name.toLowerCase();
            if (name.endsWith('.gb') || name.endsWith('.gbk') || name.endsWith('.genbank')) {
                validFiles.push(fileInput.files[i].name);
            }
        }

        if (validFiles.length === 0) {
            showError('bulkFileError', 'No valid GenBank files selected (.gb, .gbk, or .genbank)');
            return;
        }

        fileCount.textContent = `${validFiles.length} file${validFiles.length !== 1 ? 's' : ''} selected`;
        filePrompt.style.display = 'none';
        fileList.style.display = 'flex';
        clearError('bulkFileError');

        // Build the per-file MoClo level rows
        const levelGroup = document.getElementById('bulkLevelGroup');
        const rows = document.getElementById('bulkFileRows');
        if (levelGroup && rows) {
            rows.innerHTML = '';
            validFiles.forEach((fname) => {
                const guess = inferMocloLevel(fname);
                const initial = guess || 'backbone';
                const row = document.createElement('div');
                row.className = 'bulk-file-row';
                row.dataset.filename = fname;
                const label = document.createElement('span');
                label.className = 'fname';
                label.textContent = fname;
                const tag = document.createElement('span');
                tag.className = 'fname-hint';
                label.appendChild(document.createTextNode(' '));
                label.appendChild(tag);
                const controls = document.createElement('span');
                controls.className = 'bulk-file-controls';

                // Part type override (parts only; the backbone endpoint ignores it)
                const typeSel = document.createElement('select');
                typeSel.className = 'bulk-file-parttype form-control';
                const typeGuess = inferPartType(fname);

                const sel = document.createElement('select');
                sel.className = 'bulk-file-level form-control';
                sel.innerHTML =
                    '<option value="backbone">Backbone</option>' +
                    '<option value="0">Level 0 (BsaI)</option>' +
                    '<option value="1">Level 1 (BpiI)</option>' +
                    '<option value="2">Level 2 (BsaI)</option>';
                sel.value = initial;

                // Rebuild the type options to match the chosen category, keeping
                // the current pick when it is still valid.
                const syncTypeControl = () => {
                    if (sel.value === 'backbone') {
                        typeSel.style.display = 'none';
                        return;
                    }
                    typeSel.style.display = '';
                    const prev = typeSel.value;
                    typeSel.innerHTML = partTypeOptionsHtml(sel.value);
                    const opts = Array.from(typeSel.options).map((o) => o.value);
                    typeSel.value = opts.includes(prev)
                        ? prev
                        : (opts.includes(typeGuess) ? typeGuess : '');
                };
                syncTypeControl();
                const paintTag = () => {
                    tag.classList.remove('changed', 'backbone');
                    if (sel.value === initial && guess) {
                        tag.textContent = 'from filename';
                        tag.title = `Level ${guess} read from the filename`;
                    } else if (sel.value === initial) {
                        tag.classList.add('backbone');
                        tag.textContent = 'no level token, treated as backbone';
                        tag.title = 'Rename with an _L0 / _L1 token to register as a part';
                    } else if (sel.value === 'backbone') {
                        tag.classList.add('backbone', 'changed');
                        tag.textContent = 'backbone';
                        tag.title = '';
                    } else {
                        tag.classList.add('changed');
                        tag.textContent = 'manual';
                        tag.title = '';
                    }
                };
                paintTag();
                sel.addEventListener('change', () => { paintTag(); syncTypeControl(); });
                row.appendChild(label);
                controls.appendChild(typeSel);
                controls.appendChild(sel);
                row.appendChild(controls);
                rows.appendChild(row);
            });
            levelGroup.style.display = 'block';
        }
    }
}

/**
 * Handle bulk upload form submission
 */
async function handleBulkSubmit(event) {
    event.preventDefault();

    const fileInput = document.getElementById('bulkFiles');
    const submitBtn = document.getElementById('bulkSubmitButton');
    const progressDiv = document.getElementById('bulkProgress');
    const progressBar = document.getElementById('bulkProgressBar');
    const progressText = document.getElementById('bulkProgressText');
    const resultsDiv = document.getElementById('bulkResults');

    // Validate files
    if (!fileInput.files || fileInput.files.length === 0) {
        showError('bulkFileError', 'Please select at least one GenBank file');
        return;
    }

    // Filter valid files
    const files = [];
    for (let i = 0; i < fileInput.files.length; i++) {
        const name = fileInput.files[i].name.toLowerCase();
        if (name.endsWith('.gb') || name.endsWith('.gbk') || name.endsWith('.genbank')) {
            files.push(fileInput.files[i]);
        }
    }

    if (files.length === 0) {
        showError('bulkFileError', 'No valid GenBank files found (.gb, .gbk, or .genbank)');
        return;
    }

    // Map each file to its chosen category and part type from the per-file rows.
    // Category: 'backbone' (default when no level token) or '0' / '1' / '2'.
    const categoryFor = {};
    const partTypeFor = {};
    document.querySelectorAll('#bulkFileRows .bulk-file-row').forEach((r) => {
        const s = r.querySelector('.bulk-file-level');
        const t = r.querySelector('.bulk-file-parttype');
        categoryFor[r.dataset.filename] = s ? s.value : 'backbone';
        partTypeFor[r.dataset.filename] = t ? t.value : '';
    });

    // Get optional lab source
    const labSource = document.getElementById('bulkLabSource').value.trim();

    // Show progress
    submitBtn.disabled = true;
    submitBtn.textContent = 'Uploading...';
    progressDiv.style.display = 'block';
    resultsDiv.innerHTML = '';

    let successCount = 0;
    let failCount = 0;
    let duplicateCount = 0;

    for (let i = 0; i < files.length; i++) {
        const original = files[i];
        const category = categoryFor[original.name] || 'backbone';
        const isBackbone = category === 'backbone';
        const level = isBackbone ? '' : category;
        const partType = isBackbone ? '' : (partTypeFor[original.name] || '');
        // For a part, rename the file so its name carries the level token
        // before it is parsed. Backbone files are sent as-is.
        const newName = nameWithLevel(original.name, level);
        const file = renameFile(original, newName);
        const renamed = file.name !== original.name;

        if (renamed) {
            const rowEl = document.querySelector(
                `#bulkFileRows .bulk-file-row[data-filename="${(window.CSS && CSS.escape) ? CSS.escape(original.name) : original.name}"]`
            );
            if (rowEl) {
                const lbl = rowEl.querySelector('.fname');
                if (lbl && lbl.firstChild) lbl.firstChild.textContent = file.name;
                rowEl.dataset.filename = file.name;
            }
        }

        const pct = Math.round(((i + 1) / files.length) * 100);
        progressBar.style.width = pct + '%';
        progressText.textContent = `${i + 1} / ${files.length}`;

        // Build form data for this file
        const formData = new FormData();
        formData.append('file', file);
        if (!isBackbone && labSource) {
            formData.append('lab_source', labSource);
        }
        if (level !== '') {
            formData.append('level', level);
        }
        if (partType !== '') {
            formData.append('part_type', partType);
        }
        const endpoint = isBackbone ? '/api/backbones' : '/api/parts';

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });

            const data = await response.json();

            const shown = renamed
                ? `${escapeHtml(original.name)} → ${escapeHtml(file.name)}`
                : escapeHtml(file.name);
            if (response.ok) {
                successCount++;
                const obj = data.part || data.backbone || {};
                const objName = obj.name || file.name;
                const kindNote = isBackbone
                    ? ' <span style="color:#6b7280;">— backbone</span>'
                    : (data.level ? ` (Level ${escapeHtml(String(data.level))})` : '');
                const renameNote = renamed ? ` <span style="color:#6b7280;">— renamed to ${escapeHtml(file.name)}</span>` : '';
                resultsDiv.innerHTML += `<div style="color: #16a34a;">✓ ${escapeHtml(objName)}${kindNote} — uploaded${renameNote}</div>`;
                if (data.coding_warning) {
                    resultsDiv.innerHTML += `<div style="color: #d97706; margin-left: 1rem;">⚠ ${escapeHtml(data.coding_warning)}</div>`;
                }
            } else if (response.status === 409) {
                duplicateCount++;
                resultsDiv.innerHTML += `<div style="color: #d97706;">⚠ ${shown} — ${data.error || data.message || 'duplicate'}</div>`;
            } else {
                failCount++;
                resultsDiv.innerHTML += `<div style="color: #dc2626;">✗ ${shown} — ${data.error || data.message || 'failed'}</div>`;
            }
        } catch (error) {
            failCount++;
            resultsDiv.innerHTML += `<div style="color: #dc2626;">✗ ${escapeHtml(original.name)} — ${error.message}</div>`;
        }

        // Scroll results to bottom
        resultsDiv.scrollTop = resultsDiv.scrollHeight;
    }

    // Done
    submitBtn.disabled = false;
    submitBtn.textContent = 'Upload All Parts';
    progressBar.style.width = '100%';

    // Summary
    let summary = `<div style="margin-top: 0.75rem; padding: 0.5rem; background: var(--bg-color); border-radius: 4px; font-weight: 600;">`;
    summary += `Done! ${successCount} uploaded`;
    if (duplicateCount > 0) summary += `, ${duplicateCount} duplicates skipped`;
    if (failCount > 0) summary += `, ${failCount} failed`;
    summary += `</div>`;
    resultsDiv.innerHTML += summary;

    if (successCount > 0) {
        showFlashMessage(`${successCount} part${successCount !== 1 ? 's' : ''} uploaded successfully!`, 'success');
    }
}

/**
 * Escape HTML for safe display
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
