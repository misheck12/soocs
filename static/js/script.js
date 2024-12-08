// Event listener for adding a new team
document.getElementById('add-team-form').addEventListener('submit', function(event) {
    event.preventDefault();  // Prevent the default form submission behavior

    // Get the form data
    const teamName = document.getElementById('team-name').value;
    const teamLogo = document.getElementById('team-logo').value;

    // Send the data to the server
    fetch('/add-team', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            team_name: teamName,
            team_logo: teamLogo
        })
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);  // Display a message upon successful addition
        // Optionally, reset the form fields
        document.getElementById('add-team-form').reset();
    })
    .catch(error => console.error('Error:', error));  // Log any errors
});

// Event listener for generating fixtures
document.getElementById('generate-fixtures-button').addEventListener('click', function() {
    fetch('/generate-fixtures', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            alert(data.message);  // Display a message upon successful fixture generation
            loadFixtures();  // Refresh the fixtures table
        })
        .catch(error => console.error('Error:', error));  // Log any errors
});

// Function to load fixtures and update the fixtures table
function loadFixtures() {
    fetch('/fixtures')
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById('fixtures-table').querySelector('tbody');
            tableBody.innerHTML = '';  // Clear the existing table body content
            data.fixtures.forEach(fixture => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${fixture.HomeTeamName}</td>
                    <td>${fixture.AwayTeamName}</td>
                    <td>${fixture.MatchDate}</td>
                `;
                tableBody.appendChild(row);  // Add the new row to the table body
            });
        })
        .catch(error => console.error('Error:', error));  // Log any errors
}

// Function to load standings and update the standings table
function loadStandings() {
    fetch('/standings')
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById('standings-table-body');
            tableBody.innerHTML = '';  // Clear the existing table body content
            data.standings.forEach(team => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><img src="${team.TeamLogo}" alt="${team.TeamName} Logo" width="50"></td>
                    <td>${team.TeamName}</td>
                    <td>${team.Points}</td>
                    <td>${team.Wins}</td>
                    <td>${team.Draws}</td>
                    <td>${team.Losses}</td>
                    <td>${team.GoalDifference}</td>
                    <td>${team.GoalsScored}</td>
                `;
                tableBody.appendChild(row);  // Add the new row to the table body
            });
        })
        .catch(error => console.error('Error:', error));  // Log any errors
}

// Load fixtures on page load
window.onload = function() {
    loadFixtures();  // Load fixtures when the page is loaded
    loadStandings();  // Load standings when the page is loaded
}
