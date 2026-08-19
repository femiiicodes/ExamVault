// Register
const registerForm = document.getElementById('registerForm');

if (registerForm) {

    registerForm.addEventListener('submit', async function(event) {

        event.preventDefault();

        const form = event.target;
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        // Check passwords
        if (data.password !== data.confirm_password) {
            alert('Passwords do not match');
            return;
        }

        const payload = {
            first_name: data.first_name,
            last_name: data.last_name,
            email: data.email,
            level: data.level,
            department: data.department,
            college: data.college,
            role: data.role,
            password: data.password
        };

        try {

            const response = await fetch('/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                window.location.href = '/';
            }

            else {
                const errorData = await response.json();
                alert(`Error: ${errorData.detail}`);
            }

        }

        catch (error) {
            console.error('Error:', error);
            alert('Please try again later!');
        }
    });
}


// // Login

// const loginForm = document.getElementById('loginForm');

// if (loginForm) {

//     loginForm.addEventListener('submit', async function(event) {

//         event.preventDefault();

//         const form = event.target;
//         const formData = new FormData(form);

//         const payload = new URLSearchParams();

//         for (const [key, value] of formData.entries()) {
//             payload.append(key, value);
//         }

//         try {

//             const response = await fetch('/auth/token', {
//                 method: 'POST',
//                 headers: {
//                     'Content-Type': 'application/x-www-form-urlencoded'
//                 },
//                 body: payload
//             });

//             if (response.ok) {
//                 window.location.href = '/';
//             }

//             else {
//                 const errorData = await response.json();
//                 alert(`Error: ${errorData.detail}`);
//             }

//         }

//         catch (error) {
//             console.log('Error:', error);
//             alert('Please try again');
//         }
//     });
// }