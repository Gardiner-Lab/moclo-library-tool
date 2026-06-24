/**
 * Main JavaScript file for MoClo Library Tool
 * Contains utility functions and common functionality
 */

// API base URL
const API_BASE_URL = '/api';

/**
 * Make an API request with proper error handling
 * @param {string} url - The API endpoint URL
 * @param {object} options - Fetch options
 * @returns {Promise<object>} - The response data
 */
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            credentials: 'same-origin', // Include cookies for session management
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        return data;
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

/**
 * Display an error message in a form
 * @param {string} elementId - The ID of the error message element
 * @param {string} message - The error message to display
 */
function showError(elementId, message) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
}

/**
 * Clear an error message
 * @param {string} elementId - The ID of the error message element
 */
function clearError(elementId) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.textContent = '';
        errorElement.style.display = 'none';
    }
}

/**
 * Clear all error messages in a form
 * @param {HTMLFormElement} form - The form element
 */
function clearAllErrors(form) {
    const errorElements = form.querySelectorAll('.error-message');
    errorElements.forEach(element => {
        element.textContent = '';
        element.style.display = 'none';
    });

    const inputElements = form.querySelectorAll('.form-control');
    inputElements.forEach(element => {
        element.classList.remove('error');
    });
}

/**
 * Set loading state on a button
 * @param {HTMLButtonElement} button - The button element
 * @param {boolean} loading - Whether to show loading state
 */
function setButtonLoading(button, loading) {
    if (loading) {
        button.disabled = true;
        button.classList.add('loading');
        button.dataset.originalText = button.textContent;
    } else {
        button.disabled = false;
        button.classList.remove('loading');
        if (button.dataset.originalText) {
            button.textContent = button.dataset.originalText;
        }
    }
}

/**
 * Validate a form field
 * @param {HTMLInputElement} input - The input element
 * @returns {boolean} - Whether the field is valid
 */
function validateField(input) {
    const errorId = input.id + 'Error';
    clearError(errorId);
    input.classList.remove('error');

    if (!input.value.trim()) {
        showError(errorId, `${input.labels[0]?.textContent || 'This field'} is required`);
        input.classList.add('error');
        return false;
    }

    if (input.minLength && input.minLength > 0 && input.value.length < input.minLength) {
        showError(errorId, `${input.labels[0]?.textContent || 'This field'} must be at least ${input.minLength} characters`);
        input.classList.add('error');
        return false;
    }

    if (input.maxLength && input.maxLength > 0 && input.value.length > input.maxLength) {
        showError(errorId, `${input.labels[0]?.textContent || 'This field'} must be at most ${input.maxLength} characters`);
        input.classList.add('error');
        return false;
    }

    return true;
}

/**
 * Show a flash message
 * @param {string} message - The message to display
 * @param {string} category - The message category (success, error, warning, info)
 */
function showFlashMessage(message, category = 'info') {
    const container = document.querySelector('.main-content .container');
    if (!container) return;

    const alert = document.createElement('div');
    alert.className = `alert alert-${category}`;
    alert.textContent = message;

    // Insert at the beginning of the container
    container.insertBefore(alert, container.firstChild);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alert.style.opacity = '0';
        alert.style.transition = 'opacity 0.3s';
        setTimeout(() => alert.remove(), 300);
    }, 5000);
}

// Export functions for use in other modules
window.apiRequest = apiRequest;
window.showError = showError;
window.clearError = clearError;
window.clearAllErrors = clearAllErrors;
window.setButtonLoading = setButtonLoading;
window.validateField = validateField;
window.showFlashMessage = showFlashMessage;
