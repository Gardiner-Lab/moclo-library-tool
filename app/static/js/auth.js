/**
 * Authentication JavaScript for login and registration forms
 */

/**
 * Initialize the login form
 */
function initLoginForm() {
    const form = document.getElementById('loginForm');
    if (!form) return;

    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const submitButton = form.querySelector('button[type="submit"]');

    // Add real-time validation
    usernameInput.addEventListener('blur', () => validateField(usernameInput));
    passwordInput.addEventListener('blur', () => validateField(passwordInput));

    // Clear errors on input
    usernameInput.addEventListener('input', () => {
        clearError('usernameError');
        clearError('formError');
        usernameInput.classList.remove('error');
    });
    passwordInput.addEventListener('input', () => {
        clearError('passwordError');
        clearError('formError');
        passwordInput.classList.remove('error');
    });

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearAllErrors(form);

        // Validate fields
        const usernameValid = validateField(usernameInput);
        const passwordValid = validateField(passwordInput);

        if (!usernameValid || !passwordValid) {
            return;
        }

        // Submit login request
        setButtonLoading(submitButton, true);

        try {
            const response = await apiRequest('/api/auth/login', {
                method: 'POST',
                body: JSON.stringify({
                    username: usernameInput.value.trim(),
                    password: passwordInput.value,
                }),
            });

            // Login successful - redirect to protocol page
            window.location.href = '/protocol';
        } catch (error) {
            setButtonLoading(submitButton, false);
            
            // Display error message
            const errorMessage = error.message || 'Login failed. Please try again.';
            showError('formError', errorMessage);
            
            // Mark fields as error
            usernameInput.classList.add('error');
            passwordInput.classList.add('error');
        }
    });
}

/**
 * Initialize the registration form
 */
function initRegisterForm() {
    const form = document.getElementById('registerForm');
    if (!form) return;

    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const submitButton = form.querySelector('button[type="submit"]');

    // Add real-time validation
    usernameInput.addEventListener('blur', () => validateField(usernameInput));
    passwordInput.addEventListener('blur', () => validatePasswordField(passwordInput));
    confirmPasswordInput.addEventListener('blur', () => validateConfirmPassword());

    // Clear errors on input
    usernameInput.addEventListener('input', () => {
        clearError('usernameError');
        clearError('formError');
        usernameInput.classList.remove('error');
    });
    passwordInput.addEventListener('input', () => {
        clearError('passwordError');
        clearError('formError');
        passwordInput.classList.remove('error');
    });
    confirmPasswordInput.addEventListener('input', () => {
        clearError('confirmPasswordError');
        clearError('formError');
        confirmPasswordInput.classList.remove('error');
    });

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearAllErrors(form);

        // Validate fields
        const usernameValid = validateField(usernameInput);
        const passwordValid = validatePasswordField(passwordInput);
        const confirmPasswordValid = validateConfirmPassword();

        if (!usernameValid || !passwordValid || !confirmPasswordValid) {
            return;
        }

        // Submit registration request
        setButtonLoading(submitButton, true);

        try {
            const response = await apiRequest('/api/auth/register', {
                method: 'POST',
                body: JSON.stringify({
                    username: usernameInput.value.trim(),
                    password: passwordInput.value,
                }),
            });

            // Registration successful - show message and redirect to login
            showFlashMessage('Registration successful! Please log in.', 'success');
            setTimeout(() => {
                window.location.href = '/login';
            }, 1500);
        } catch (error) {
            setButtonLoading(submitButton, false);
            
            // Display error message
            const errorMessage = error.message || 'Registration failed. Please try again.';
            
            // Check if it's a username conflict
            if (errorMessage.toLowerCase().includes('username') || 
                errorMessage.toLowerCase().includes('already exists')) {
                showError('usernameError', errorMessage);
                usernameInput.classList.add('error');
            } else {
                showError('formError', errorMessage);
            }
        }
    });

    /**
     * Validate password field with additional checks
     */
    function validatePasswordField(input) {
        const errorId = input.id + 'Error';
        clearError(errorId);
        input.classList.remove('error');

        if (!input.value) {
            showError(errorId, 'Password is required');
            input.classList.add('error');
            return false;
        }

        if (input.value.length < 8) {
            showError(errorId, 'Password must be at least 8 characters');
            input.classList.add('error');
            return false;
        }

        return true;
    }

    /**
     * Validate confirm password field
     */
    function validateConfirmPassword() {
        const errorId = 'confirmPasswordError';
        clearError(errorId);
        confirmPasswordInput.classList.remove('error');

        if (!confirmPasswordInput.value) {
            showError(errorId, 'Please confirm your password');
            confirmPasswordInput.classList.add('error');
            return false;
        }

        if (confirmPasswordInput.value !== passwordInput.value) {
            showError(errorId, 'Passwords do not match');
            confirmPasswordInput.classList.add('error');
            return false;
        }

        return true;
    }
}

// Export functions
window.initLoginForm = initLoginForm;
window.initRegisterForm = initRegisterForm;
