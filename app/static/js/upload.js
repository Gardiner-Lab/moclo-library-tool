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
}

/**
 * Initialize toggle buttons for switching between upload methods
 */
function initToggleButtons() {
    const manualToggle = document.getElementById('manualToggle');
    const genbankToggle = document.getElementById('genbankToggle');
    const manualCard = document.getElementById('manualUploadCard');
    const genbankCard = document.getElementById('genbankUploadCard');
    
    manualToggle.addEventListener('click', () => {
        manualToggle.classList.add('active');
        genbankToggle.classList.remove('active');
        manualCard.style.display = 'block';
        genbankCard.style.display = 'none';
    });
    
    genbankToggle.addEventListener('click', () => {
        genbankToggle.classList.add('active');
        manualToggle.classList.remove('active');
        genbankCard.style.display = 'block';
        manualCard.style.display = 'none';
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
        if (!file.name.toLowerCase().endsWith('.gb') && !file.name.toLowerCase().endsWith('.genbank')) {
            showError('genbankFileError', 'Please select a GenBank file (.gb or .genbank)');
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
    
    // Set loading state
    const submitButton = document.getElementById('genbankSubmitButton');
    const originalText = submitButton.textContent;
    setButtonLoading(submitButton, true);
    submitButton.textContent = 'Processing...';
    
    try {
        // Submit to API (multipart/form-data)
        const response = await fetch('/api/parts', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Upload failed');
        }
        
        const data = await response.json();
        
        // Success - show message with details
        let message = 'Part uploaded successfully from GenBank file!';
        if (data.detected_type) {
            message += ` (Detected type: ${data.detected_type})`;
        }
        showFlashMessage(message, 'success');
        
        // Redirect to parts browser after a short delay
        setTimeout(() => {
            window.location.href = '/parts';
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
