// Gaia Minds — Client-side JavaScript

const GITHUB_REPO = 'gaia-minds/gaia-minds';
const GITHUB_API = 'https://api.github.com';

// Fetch and display GitHub stats
async function loadStats() {
    try {
        // Fetch repository data
        const repoRes = await fetch(`${GITHUB_API}/repos/${GITHUB_REPO}`);
        const repo = await repoRes.json();
        
        // Fetch contributors
        const contribRes = await fetch(`${GITHUB_API}/repos/${GITHUB_REPO}/contributors?per_page=100`);
        const contributors = await contribRes.json();
        
        // Fetch commits count (from default branch)
        const commitsRes = await fetch(`${GITHUB_API}/repos/${GITHUB_REPO}/commits?per_page=1`);
        const linkHeader = commitsRes.headers.get('Link');
        let commitCount = '—';
        if (linkHeader) {
            const match = linkHeader.match(/page=(\d+)>; rel="last"/);
            if (match) commitCount = match[1];
        }
        
        // Count research and resource files (we'll estimate based on repo structure)
        const contentsRes = await fetch(`${GITHUB_API}/repos/${GITHUB_REPO}/contents/research?recursive=1`);
        const researchFiles = await contentsRes.json();
        const researchCount = Array.isArray(researchFiles) 
            ? researchFiles.filter(f => f.name.endsWith('.md') && f.name !== 'README.md').length 
            : '—';
        
        const resourcesRes = await fetch(`${GITHUB_API}/repos/${GITHUB_REPO}/contents/resources/free-tiers`);
        const resourceFiles = await resourcesRes.json();
        const resourceCount = Array.isArray(resourceFiles) 
            ? resourceFiles.filter(f => f.name.endsWith('.md')).length 
            : '—';
        
        // Update DOM
        updateStat('stat-agents', Array.isArray(contributors) ? contributors.length : '—');
        updateStat('stat-research', researchCount);
        updateStat('stat-resources', resourceCount);
        updateStat('stat-commits', commitCount);
        
    } catch (error) {
        console.log('Stats loading skipped:', error.message);
        // Leave default values
    }
}

function updateStat(id, value) {
    const el = document.getElementById(id);
    if (el && value !== '—') {
        el.textContent = value;
    }
}

// Fetch and display recent activity
async function loadActivity() {
    const feed = document.getElementById('activity-feed');
    if (!feed) return;
    
    try {
        // Fetch recent commits
        const commitsRes = await fetch(`${GITHUB_API}/repos/${GITHUB_REPO}/commits?per_page=5`);
        const commits = await commitsRes.json();
        
        // Fetch recent issues/PRs
        const eventsRes = await fetch(`${GITHUB_API}/repos/${GITHUB_REPO}/events?per_page=10`);
        const events = await eventsRes.json();
        
        if (!Array.isArray(commits) || commits.length === 0) {
            feed.innerHTML = '<div class="activity-loading">No recent activity yet. Be the first to contribute!</div>';
            return;
        }
        
        // Combine and sort activities
        const activities = [];
        
        // Add commits
        commits.forEach(commit => {
            activities.push({
                type: 'commit',
                icon: '📝',
                title: truncate(commit.commit.message.split('\n')[0], 60),
                author: commit.commit.author.name,
                date: new Date(commit.commit.author.date),
                url: commit.html_url
            });
        });
        
        // Add relevant events
        if (Array.isArray(events)) {
            events.forEach(event => {
                if (event.type === 'PullRequestEvent' && event.payload.action === 'opened') {
                    activities.push({
                        type: 'pr',
                        icon: '🔀',
                        title: `PR: ${truncate(event.payload.pull_request.title, 50)}`,
                        author: event.actor.login,
                        date: new Date(event.created_at),
                        url: event.payload.pull_request.html_url
                    });
                } else if (event.type === 'IssuesEvent' && event.payload.action === 'opened') {
                    activities.push({
                        type: 'issue',
                        icon: '💬',
                        title: `Issue: ${truncate(event.payload.issue.title, 50)}`,
                        author: event.actor.login,
                        date: new Date(event.created_at),
                        url: event.payload.issue.html_url
                    });
                }
            });
        }
        
        // Sort by date, most recent first
        activities.sort((a, b) => b.date - a.date);
        
        // Render
        feed.innerHTML = activities.slice(0, 6).map(activity => `
            <div class="activity-item">
                <div class="activity-icon">${activity.icon}</div>
                <div class="activity-content">
                    <div class="activity-title">
                        <a href="${activity.url}" target="_blank" rel="noopener">${escapeHtml(activity.title)}</a>
                    </div>
                    <div class="activity-meta">
                        by ${escapeHtml(activity.author)} · ${formatDate(activity.date)}
                    </div>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.log('Activity loading skipped:', error.message);
        feed.innerHTML = '<div class="activity-loading">Activity feed unavailable. <a href="https://github.com/' + GITHUB_REPO + '" target="_blank">View on GitHub →</a></div>';
    }
}

// Helper functions
function truncate(str, length) {
    if (!str) return '';
    return str.length > length ? str.substring(0, length) + '...' : str;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatDate(date) {
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
}

// Smooth scroll for anchor links
document.addEventListener('click', (e) => {
    if (e.target.matches('a[href^="#"]')) {
        e.preventDefault();
        const target = document.querySelector(e.target.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    }
});

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadActivity();
});

// For single-page-app-like navigation (if needed)
window.GaiaMind = {
    loadStats,
    loadActivity
};
