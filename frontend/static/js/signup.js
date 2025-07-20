document.getElementById('register-form').addEventListener('submit', async function (event) {
    event.preventDefault(); // Prevents the default form submission

    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const password2 = document.getElementById('password2').value;
    const errorMessageDiv = document.getElementById('error-message');

    errorMessageDiv.classList.add('hidden'); // Hide previous error messages
    errorMessageDiv.textContent = ''; // Clear error message text

    try {
        const response = await fetch('/api/register/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') // Get CSRF token for security
            },
            body: JSON.stringify({ username, email, password, password2 }) // Send data as JSON
        });

        const data = await response.json(); // Parse the JSON response from the server

        if (response.ok) { // If the HTTP response is 2xx (success)
            alert('Registro bem-sucedido! Agora faça login.'); // Success alert
            window.location.href = '/accounts/login/'; // Redirect to the login page
        } else { // If the HTTP response is an error (e.g., 400, 401)
            let errors = '';
            // Iterate over the error data to build a comprehensive message
            for (const key in data) {
                if (Array.isArray(data[key])) {
                    errors += `${key}: ${data[key].join(', ')}\n`;
                } else {
                    errors += `${key}: ${data[key]}\n`;
                }
            }
            errorMessageDiv.textContent = errors; // Display the error message from the server
            errorMessageDiv.classList.remove('hidden'); // Show the error div
        }
    } catch (error) { // Handle network errors or other unexpected errors
        errorMessageDiv.textContent = 'Ocorreu um erro inesperado. Tente novamente.';
        errorMessageDiv.classList.remove('hidden');
        console.error('Erro de registro:', error);
    }
});

// Helper function to get CSRF token from cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
