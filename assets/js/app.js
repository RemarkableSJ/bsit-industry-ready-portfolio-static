(function () {
  'use strict';

  const STORAGE_KEY = 'bsitIndustryReadyPortfolio.v1';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const clone = (value) => JSON.parse(JSON.stringify(value));

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
  }

  function multiline(value) {
    return escapeHtml(value).replace(/\r?\n/g, '<br>');
  }

  function safeUrl(value, allowMailto = true) {
    const raw = String(value || '').trim();
    if (!raw) return '';
    if (allowMailto && /^mailto:/i.test(raw)) return raw;
    if (/^https?:\/\//i.test(raw)) return raw;
    return '';
  }

  function linkOrPlaceholder(url, text, className = 'btn btn-sm btn-outline-primary') {
    const goodUrl = safeUrl(url);
    if (!goodUrl) return `<span class="link-placeholder">${escapeHtml(text)} · link not added</span>`;
    return `<a class="${className}" href="${escapeHtml(goodUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(text)} <span aria-hidden="true">↗</span></a>`;
  }

  function safeResumeDataUrl(value) {
    const raw = String(value || '');
    return /^data:application\/pdf;base64,[A-Za-z0-9+/=]+$/.test(raw) ? raw : '';
  }

  function initials(name) {
    const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    return parts.slice(0, 2).map((part) => part[0].toUpperCase()).join('') || 'IT';
  }

  function wordCount(value) {
    const trimmed = String(value || '').trim();
    return trimmed ? trimmed.split(/\s+/).length : 0;
  }

  function getStarterData() {
    return clone(window.defaultPortfolio);
  }

  function loadData() {
    // Static edition: published content is loaded from assets/js/default-data.js.
    const serverData = window.defaultPortfolio;
    return serverData && serverData.profile && Array.isArray(serverData.projects)
      ? clone(serverData)
      : getStarterData();
  }

  let data = loadData();
  let draft = null;
  let activeEditorKey = 'profile';

  const schemas = {
    profile: {
      label: 'Professional Profile', type: 'object', key: 'profile',
      help: 'Replace sample text with accurate personal information. Only list skills you can demonstrate.',
      fields: [
        { key: 'name', label: 'Full name', type: 'text' },
        { key: 'role', label: 'Professional headline', type: 'text' },
        { key: 'specialization', label: 'BSIT specialization / preferred IT field', type: 'text' },
        { key: 'targetPosition', label: 'Target IT position', type: 'text' },
        { key: 'location', label: 'Location (city/region is enough)', type: 'text' },
        { key: 'program', label: 'Program', type: 'text' },
        { key: 'school', label: 'School / institution (optional)', type: 'text' },
        { key: 'section', label: 'Section (optional)', type: 'text' },
        { key: 'academicYear', label: 'Academic year (optional)', type: 'text' },
        { key: 'instructor', label: 'Instructor / adviser (optional)', type: 'text' },
        { key: 'professionalStatement', label: 'Professional statement', type: 'textarea' },
        { key: 'aboutMe', label: 'About Me (aim for 150–250 words)', type: 'textarea', rows: 8 },
        { key: 'email', label: 'Professional email', type: 'text' },
        { key: 'phone', label: 'Phone (optional)', type: 'text' },
        { key: 'github', label: 'GitHub profile URL', type: 'text' },
        { key: 'linkedin', label: 'LinkedIn profile URL', type: 'text' },
        { key: 'portfolioUrl', label: 'Portfolio URL (optional)', type: 'text' },
        { key: 'photoUrl', label: 'Professional photo URL (optional)', type: 'text' }
      ]
    },
    skills: {
      label: 'Technical Skills', type: 'collection', key: 'skills',
      help: 'Add, edit, or remove skill rows. A skill level should match what you can demonstrate, and evidence should link to something verifiable.',
      fields: [
        { key: 'category', label: 'Category', type: 'text' },
        { key: 'skill', label: 'Skill', type: 'text' },
        { key: 'level', label: 'Self-assessed level', type: 'select', options: ['Not yet assessed', 'Learning', 'Beginner', 'Intermediate', 'Advanced'] },
        { key: 'evidence', label: 'Evidence / project', type: 'textarea' }
      ],
      create: { category: 'New category', skill: '', level: 'Not yet assessed', evidence: '' }
    },
    projects: {
      label: 'Projects (3 required)', type: 'collection', key: 'projects',
      help: 'The PDF asks for a web/application project, a data/database project, and a specialization project. These starter records are plans, not proof of completed work.',
      fields: [
        { key: 'title', label: 'Project title', type: 'text' },
        { key: 'type', label: 'Project category', type: 'text' },
        { key: 'status', label: 'Status', type: 'select', options: ['Planned', 'In progress', 'Needs evidence', 'Completed'] },
        { key: 'overview', label: 'Overview', type: 'textarea' },
        { key: 'problem', label: 'Problem statement', type: 'textarea' },
        { key: 'objectives', label: 'Objectives', type: 'textarea' },
        { key: 'functionalRequirements', label: 'Functional requirements', type: 'textarea' },
        { key: 'nonFunctionalRequirements', label: 'Non-functional requirements', type: 'textarea' },
        { key: 'existingProposedSystem', label: 'Existing system / proposed system', type: 'textarea' },
        { key: 'useCases', label: 'Use cases / actors / UML', type: 'textarea' },
        { key: 'interfaceDesign', label: 'Interface design / wireframes', type: 'textarea' },
        { key: 'targetUsers', label: 'Target users', type: 'textarea' },
        { key: 'technologies', label: 'Technologies actually used', type: 'textarea' },
        { key: 'features', label: 'Features / requirements', type: 'textarea' },
        { key: 'architecture', label: 'System architecture', type: 'textarea' },
        { key: 'databaseDesign', label: 'Database design / ERD', type: 'textarea' },
        { key: 'liveDemo', label: 'Live demo URL', type: 'text' },
        { key: 'githubUrl', label: 'GitHub repository URL', type: 'text' },
        { key: 'readmeUrl', label: 'README / documentation URL', type: 'text' },
        { key: 'screenshots', label: 'Screenshots (one URL per line or a note)', type: 'textarea' },
        { key: 'installation', label: 'Installation / setup instructions', type: 'textarea' },
        { key: 'usage', label: 'How to use the system', type: 'textarea' },
        { key: 'testing', label: 'Testing and results', type: 'textarea' },
        { key: 'bugsAndCorrections', label: 'Bugs and corrections', type: 'textarea' },
        { key: 'deploymentNotes', label: 'Hosting / deployment / configuration notes', type: 'textarea' },
        { key: 'limitations', label: 'Limitations', type: 'textarea' },
        { key: 'futureImprovements', label: 'Future improvements', type: 'textarea' },
        { key: 'developerRole', label: 'My role / contribution', type: 'textarea' }
      ],
      create: { title: 'New project', type: '', status: 'Planned', overview: '', problem: '', objectives: '', functionalRequirements: '', nonFunctionalRequirements: '', existingProposedSystem: '', useCases: '', interfaceDesign: '', targetUsers: '', technologies: '', features: '', architecture: '', databaseDesign: '', liveDemo: '', githubUrl: '', readmeUrl: '', screenshots: '', installation: '', usage: '', testing: '', bugsAndCorrections: '', deploymentNotes: '', limitations: '', futureImprovements: '', developerRole: '' }
    },
    troubleshooting: {
      label: 'Troubleshooting Cases (at least 5)', type: 'collection', key: 'troubleshooting',
      help: 'There are five educational examples to guide you. Personalize the diagnosis, actual fix, and lesson based on cases you genuinely worked through before submission.',
      fields: [
        { key: 'caseNumber', label: 'Case number', type: 'text' },
        { key: 'title', label: 'Case title', type: 'text' },
        { key: 'status', label: 'Evidence status', type: 'text' },
        { key: 'problem', label: 'Problem', type: 'textarea' },
        { key: 'possibleCauses', label: 'Possible causes', type: 'textarea' },
        { key: 'diagnosticProcedure', label: 'Diagnostic procedure', type: 'textarea' },
        { key: 'solution', label: 'Solution', type: 'textarea' },
        { key: 'lessonLearned', label: 'Lesson learned', type: 'textarea' }
      ],
      create: { caseNumber: '', title: 'New troubleshooting case', status: 'Draft — document a real case', problem: '', possibleCauses: '', diagnosticProcedure: '', solution: '', lessonLearned: '' }
    },
    securityCase: {
      label: 'Cybersecurity Case', type: 'object', key: 'securityCase',
      help: 'Explain the security issue defensively and use authorized test environments only.',
      fields: [
        { key: 'title', label: 'Case title', type: 'text' },
        { key: 'vulnerability', label: 'What is the vulnerability?', type: 'textarea' },
        { key: 'howItHappens', label: 'How can it happen?', type: 'textarea' },
        { key: 'risks', label: 'Risks / impact', type: 'textarea' },
        { key: 'prevention', label: 'Prevention', type: 'textarea' },
        { key: 'practices', label: 'Security practices', type: 'textarea' },
        { key: 'demonstration', label: 'Safe demonstration / explanation', type: 'textarea' }
      ]
    },
    aiLog: {
      label: 'AI Usage Log', type: 'collection', key: 'aiLog',
      help: 'Record real AI use and what you personally checked. Do not claim you verified something unless you actually did.',
      fields: [
        { key: 'date', label: 'Date (YYYY-MM-DD)', type: 'text' },
        { key: 'task', label: 'Task', type: 'text' },
        { key: 'assistance', label: 'AI assistance', type: 'textarea' },
        { key: 'verification', label: 'My verification / result', type: 'textarea' },
        { key: 'result', label: 'What changed / what I learned', type: 'textarea' }
      ],
      create: { date: '', task: '', assistance: '', verification: '', result: '' }
    },
    aiReflection: {
      label: 'AI Literacy Reflection', type: 'object', key: 'aiReflection',
      help: 'The PDF asks you to explain what AI helped with, what you personally verified, what you learned, and any limitations or mistakes you discovered.',
      fields: [
        { key: 'helped', label: 'What did AI help me accomplish?', type: 'textarea' },
        { key: 'verified', label: 'What did I personally verify?', type: 'textarea' },
        { key: 'learned', label: 'What did I learn from using AI?', type: 'textarea' },
        { key: 'limitations', label: 'What limitations or errors did I discover?', type: 'textarea' }
      ]
    },
    interviews: {
      label: 'Mock / Technical Interview', type: 'collection', key: 'interviews',
      help: 'Write answers in your own words and use real examples. The guidance below each default question is a prompt, not a finished personal answer.',
      fields: [
        { key: 'question', label: 'Interview question', type: 'textarea' },
        { key: 'answer', label: 'My answer / speaking notes', type: 'textarea', rows: 5 }
      ],
      create: { question: 'New interview question', answer: '' }
    },
    defensePlan: {
      label: 'Project Defense Plan', type: 'collection', key: 'defensePlan',
      help: 'The steps and durations follow the supplied PDF. Customize the talking points for your actual project and rehearse the demonstration.',
      fields: [
        { key: 'step', label: 'Presentation step', type: 'text' },
        { key: 'duration', label: 'Suggested time', type: 'text' },
        { key: 'talkingPoints', label: 'Talking points', type: 'textarea' },
        { key: 'demonstration', label: 'What to demonstrate', type: 'textarea' }
      ],
      create: { step: 'New step', duration: '', talkingPoints: '', demonstration: '' }
    },
    careerPlan: {
      label: 'Career Development Plan', type: 'object', key: 'careerPlan',
      help: 'Keep goals concrete and measurable. Revisit the plan as your skills and interests develop.',
      fields: [
        { key: 'targetPosition', label: 'Target position', type: 'textarea' },
        { key: 'targetField', label: 'Target IT field', type: 'textarea' },
        { key: 'currentSkills', label: 'Current skills', type: 'textarea' },
        { key: 'skillsToImprove', label: 'Skills to improve', type: 'textarea' },
        { key: 'technologies', label: 'Technologies to learn', type: 'textarea' },
        { key: 'certifications', label: 'Certifications to consider', type: 'textarea' },
        { key: 'sixMonthGoal', label: 'Six-month goal', type: 'textarea' },
        { key: 'oneYearGoal', label: 'One-year goal', type: 'textarea' },
        { key: 'threeYearGoal', label: 'Three-year professional goal', type: 'textarea' }
      ]
    },
    reflection: {
      label: 'Final Reflection', type: 'object', key: 'reflection',
      help: 'The PDF specifies 500–800 words. Use your own experiences and remove the prompt before submitting.',
      fields: [{ key: 'text', label: 'Reflection (500–800 words)', type: 'textarea', rows: 18 }]
    },
    certificates: {
      label: 'Certificates / Achievements', type: 'collection', key: 'certificates',
      help: 'Add genuine certificates, awards, or achievements. You can leave this list empty until you have evidence to share.',
      fields: [
        { key: 'name', label: 'Certificate / achievement', type: 'text' },
        { key: 'issuer', label: 'Issuer / organization', type: 'text' },
        { key: 'date', label: 'Date earned', type: 'text' },
        { key: 'credentialUrl', label: 'Credential URL', type: 'text' },
        { key: 'description', label: 'Description / evidence', type: 'textarea' }
      ],
      create: { name: '', issuer: '', date: '', credentialUrl: '', description: '' }
    },
    resume: {
      label: 'Resume & Download', type: 'object', key: 'resume',
      help: 'Upload a PDF resume (stored in this browser if storage allows) or enter a public URL. Keep the resume to one page as recommended by the PDF.',
      fields: [{ key: 'resumeUrl', label: 'Public resume URL (optional)', type: 'text' }]
    },
    checklist: {
      label: 'Final Portfolio Checklist', type: 'collection', key: 'checklist',
      help: 'Tick a requirement only after you have completed it. Progress is saved in this browser. This list follows the PDF checklist and final submission reminders.',
      fields: [
        { key: 'item', label: 'Requirement', type: 'text' },
        { key: 'completed', label: 'Completed?', type: 'checkbox' }
      ],
      create: { item: 'New requirement', completed: false }
    }
  };

  const editorOrder = [
    'profile', 'skills', 'projects', 'troubleshooting', 'securityCase', 'aiLog', 'aiReflection',
    'interviews', 'defensePlan', 'careerPlan', 'resume', 'certificates', 'reflection', 'checklist'
  ];

  function saveData() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      $('#saveStatus').textContent = 'Saved in this browser';
      $('#saveStatus').classList.add('status-visible');
      window.setTimeout(() => $('#saveStatus')?.classList.remove('status-visible'), 2600);
      return true;
    } catch (error) {
      console.error('Could not save portfolio content.', error);
      alert('Your browser could not save these changes. The resume file or content may be too large. Try removing a large upload, then export your content as a backup.');
      return false;
    }
  }

  function renderHero() {
    const p = data.profile;
    $('#heroName').textContent = p.name || 'Your Name';
    $('#heroRole').textContent = p.role || 'BSIT Student · Aspiring IT Professional';
    $('#heroSpecialization').textContent = p.specialization || 'Choose your preferred IT field';
    $('#heroStatement').textContent = p.professionalStatement || 'Add your professional statement in the portfolio data file.';
    $('#heroInitials').textContent = initials(p.name);
    const photo = safeUrl(p.photoUrl);
    const avatar = $('#heroAvatar');
    if (photo) {
      avatar.innerHTML = `<img src="${escapeHtml(photo)}" alt="Professional photograph of ${escapeHtml(p.name || 'portfolio owner')}" referrerpolicy="no-referrer">`;
    } else {
      avatar.innerHTML = `<span id="heroInitials">${escapeHtml(initials(p.name))}</span>`;
    }
    const resumeDataUrl = data.resume ? safeResumeDataUrl(data.resume.dataUrl) : '';
    const resumeAvailable = Boolean(data.resume && (resumeDataUrl || safeUrl(data.resume.resumeUrl)));
    const resumeCta = $('#heroResume');
    if (resumeAvailable) {
      resumeCta.removeAttribute('data-open-editor');
      resumeCta.textContent = 'Download Resume';
      resumeCta.href = resumeDataUrl || safeUrl(data.resume.resumeUrl);
      if (resumeDataUrl) { resumeCta.setAttribute('download', data.resume.fileName || 'resume.pdf'); resumeCta.removeAttribute('target'); resumeCta.removeAttribute('rel'); }
      else { resumeCta.removeAttribute('download'); resumeCta.target = '_blank'; resumeCta.rel = 'noopener noreferrer'; }
      resumeCta.classList.remove('btn-muted');
    } else {
      resumeCta.textContent = 'Add Your Resume';
      resumeCta.href = '#resume';
      resumeCta.removeAttribute('data-open-editor');
      resumeCta.removeAttribute('download');
      resumeCta.removeAttribute('target');
      resumeCta.classList.add('btn-muted');
      resumeCta.setAttribute('data-open-editor', 'resume');
    }
  }

  function renderProfile() {
    const p = data.profile;
    $('#profileContent').innerHTML = `
      <div class="profile-copy">
        <p class="eyebrow">01 / PROFESSIONAL PROFILE</p>
        <h2>About me<span class="accent-dot">.</span></h2>
        <div class="body-copy">${multiline(p.aboutMe || 'Use the portfolio data file to write a 150–250 word professional introduction.')}</div>
        <p class="word-count-inline">${wordCount(p.aboutMe)} words · Recommended range: 150–250 words</p>
        <div class="statement-box"><span class="small-label">PROFESSIONAL STATEMENT</span><p>${multiline(p.professionalStatement || 'Add your professional statement.')}</p></div>
      </div>
      <aside class="profile-aside">
        <div class="detail-card"><span class="small-label">TARGET ROLE</span><strong>${escapeHtml(p.targetPosition || 'Add a target position')}</strong></div>
        <div class="detail-card"><span class="small-label">IT FIELD</span><strong>${escapeHtml(p.specialization || 'Choose a field')}</strong></div>
        <div class="detail-card"><span class="small-label">LOCATION</span><strong>${escapeHtml(p.location || 'Add location')}</strong></div>
        <div class="detail-card"><span class="small-label">PROGRAM</span><strong>${escapeHtml(p.program || 'Bachelor of Science in Information Technology (BSIT)')}</strong></div>
        ${p.school ? `<div class="detail-card"><span class="small-label">SCHOOL</span><strong>${escapeHtml(p.school)}</strong></div>` : ''}
        ${p.section ? `<div class="detail-card"><span class="small-label">SECTION</span><strong>${escapeHtml(p.section)}</strong></div>` : ''}
        ${p.academicYear ? `<div class="detail-card"><span class="small-label">ACADEMIC YEAR</span><strong>${escapeHtml(p.academicYear)}</strong></div>` : ''}
        ${p.instructor ? `<div class="detail-card"><span class="small-label">INSTRUCTOR / ADVISER</span><strong>${escapeHtml(p.instructor)}</strong></div>` : ''}
        <div class="profile-links">${p.email && p.email.includes('@') ? `<a href="mailto:${escapeHtml(p.email)}"><span class="mini-icon">✉</span> ${escapeHtml(p.email)}</a>` : '<a href="#contact"><span class="mini-icon">✉</span> Use the contact form</a>'}${safeUrl(p.linkedin) ? `<a href="${escapeHtml(safeUrl(p.linkedin))}" target="_blank" rel="noopener noreferrer"><span class="mini-icon">in</span> LinkedIn profile ↗</a>` : ''}</div>
      </aside>`;
  }

  function renderSkills() {
    const skills = Array.isArray(data.skills) ? data.skills : [];
    const categories = [...new Set(skills.map((item) => item.category || 'Other'))];
    $('#skillsContent').innerHTML = skills.length ? `
      <div class="section-intro-row"><div><p class="eyebrow">02 / TECHNICAL SKILLS</p><h2>Skills with evidence<span class="accent-dot">.</span></h2></div><p class="section-intro">Be specific about your level. The PDF’s rule is simple: <strong>no evidence, no skill claim.</strong></p></div>
      <div class="skills-grid">${categories.map((category) => {
        const group = skills.filter((skill) => (skill.category || 'Other') === category);
        return `<article class="skill-card"><div class="skill-card-head"><span class="skill-icon">${escapeHtml(category.slice(0, 2).toUpperCase())}</span><h3>${escapeHtml(category)}</h3></div><div class="skill-list">${group.map((skill) => `<div class="skill-item"><div class="skill-title-row"><strong>${escapeHtml(skill.skill || 'Untitled skill')}</strong><span class="level-pill ${String(skill.level || '').toLowerCase().replace(/[^a-z]+/g, '-').replace(/^-|-$/g, '')}">${escapeHtml(skill.level || 'Not assessed')}</span></div><p>${multiline(skill.evidence || 'Add evidence: repository, project, lab, certificate, or coursework.')}</p></div>`).join('')}</div></article>`;
      }).join('')}</div>` : emptyState('No skills added yet', 'Add your skills and supporting evidence in the portfolio data file.', 'skills');
  }

  function renderProjects() {
    const projects = Array.isArray(data.projects) ? data.projects : [];
    $('#projectsContent').innerHTML = `<div class="section-intro-row"><div><p class="eyebrow">03 / PROJECTS</p><h2>Work that shows what I can do<span class="accent-dot">.</span></h2></div><p class="section-intro">These projects show three areas of applied work: web application development, data analysis and database use, and mobile development. Open a case study for its scope, technical details, testing status, and limitations.</p></div>
      ${projects.length ? `<div class="projects-grid">${projects.map((project, index) => {
        const status = project.status || 'Planned';
        const statusClass = status.toLowerCase().replace(/[^a-z]+/g, '-').replace(/^-|-$/g, '');
        const demoLabel = index === 0 ? 'Open Museum Demo' : '';

const demoAction = safeUrl(project.liveDemo)
    ? linkOrPlaceholder(
        project.liveDemo,
        demoLabel,
        'btn btn-sm btn-primary'
    )
    : `<span class="link-placeholder">${
        index === 1
            ? 'Online dashboard not deployed yet'
            : 'Windows desktop app · download to run'
    }</span>`;

const sourceLabel = index === 0
    ? 'Browse Source Files'
    : 'Download Source Package';

const documentationLabel = index === 1
    ? 'View Project Report'
    : 'Read Documentation';
        return `<article class="project-card"><div class="project-topline"><span class="project-number">PROJECT ${String(index + 1).padStart(2, '0')}</span><span class="status-pill ${statusClass}">${escapeHtml(status)}</span></div><p class="project-type">${escapeHtml(project.type || 'IT Project')}</p><h3>${escapeHtml(project.title || 'Untitled Project')}</h3><p class="project-overview">${multiline(project.overview || 'Add a project overview.')}</p>
          <div class="project-links"><a class="btn btn-sm btn-outline-primary" href="project.html?id=${index}">Open Case Study ↗</a>${demoAction}${linkOrPlaceholder(project.githubUrl, sourceLabel)}${linkOrPlaceholder(project.readmeUrl, documentationLabel)}</div>
          <details class="project-details"><summary>Project details & evidence</summary><div class="details-body">
            ${detailBlock('Problem statement', project.problem)}${detailBlock('Objectives', project.objectives)}${detailBlock('Functional requirements', project.functionalRequirements)}${detailBlock('Non-functional requirements', project.nonFunctionalRequirements)}${detailBlock('Existing / proposed system', project.existingProposedSystem)}${detailBlock('Use cases / UML', project.useCases)}${detailBlock('Interface design', project.interfaceDesign)}${detailBlock('Target users', project.targetUsers)}${detailBlock('Technologies', project.technologies)}${detailBlock('Features', project.features)}${detailBlock('System architecture', project.architecture)}${detailBlock('Database design', project.databaseDesign)}${detailBlock('Screenshots / diagrams', project.screenshots)}${detailBlock('Installation / setup', project.installation)}${detailBlock('How to use', project.usage)}${detailBlock('Testing & results', project.testing)}${detailBlock('Bugs and corrections', project.bugsAndCorrections)}${detailBlock('Deployment / configuration', project.deploymentNotes)}${detailBlock('My role', project.developerRole)}${detailBlock('Limitations', project.limitations)}${detailBlock('Future improvements', project.futureImprovements)}
          </div></details></article>`;
      }).join('')}</div>` : emptyState('No projects added yet', 'Add your three projects in the portfolio data file.', 'projects')}`;
  }

  function detailBlock(label, value) {
    if (!String(value || '').trim()) return '';
    return `<div class="detail-block"><h4>${escapeHtml(label)}</h4><p>${multiline(value)}</p></div>`;
  }

  function renderEvidence() {
    const items = Array.isArray(window.staticEvidence) ? window.staticEvidence : [];
    $('#evidenceContent').innerHTML = `<div class="section-intro-row"><div><p class="eyebrow">PROJECT DOCUMENTATION</p><h2>Evidence library<span class="accent-dot">.</span></h2></div><p class="section-intro">Reports and supporting files included with this static portfolio.</p></div>${items.length ? `<div class="evidence-grid">${items.map((item) => `<article class="evidence-card"><div class="evidence-file-icon">${item.type === 'pdf' ? 'PDF' : 'XLSX'}</div><div><span class="evidence-category">${escapeHtml(item.category || 'Project evidence')}</span><h3>${escapeHtml(item.title || 'Evidence file')}</h3><p>${escapeHtml(item.description || '')}</p><a href="${escapeHtml(item.url)}" class="inline-link" target="_blank" rel="noopener">View / download ↗</a></div></article>`).join('')}</div>` : `<div class="evidence-empty"><h3>Project evidence</h3><p>Open the individual project case studies and source repositories for supporting material.</p></div>`}`;
  }

  function renderTroubleshooting() {
    const cases = Array.isArray(data.troubleshooting) ? data.troubleshooting : [];
    $('#troubleshootingContent').innerHTML = `<div class="section-intro-row"><div><p class="eyebrow">04 / PROBLEM-SOLVING</p><h2>How I investigate and resolve issues<span class="accent-dot">.</span></h2></div><p class="section-intro">Each case records the issue, likely causes, diagnostic steps, response, and lesson learned. Status labels distinguish observed issues, code-review findings, and completed data-cleaning work from items that still need retesting.</p></div>
      ${cases.length ? `<div class="case-list">${cases.map((item, index) => `<details class="case-card"><summary><span class="case-number">${escapeHtml(item.caseNumber || String(index + 1).padStart(2, '0'))}</span><span class="case-heading"><strong>${escapeHtml(item.title || 'Troubleshooting case')}</strong><small>${escapeHtml(item.status || 'Draft')}</small></span><span class="summary-plus" aria-hidden="true">+</span></summary><div class="case-grid">${detailBlock('Problem', item.problem)}${detailBlock('Possible causes', item.possibleCauses)}${detailBlock('Diagnostic procedure', item.diagnosticProcedure)}${detailBlock('Solution', item.solution)}${detailBlock('Lesson learned', item.lessonLearned)}</div></details>`).join('')}</div>` : emptyState('No troubleshooting cases yet', 'Add at least five real cases before final submission.', 'troubleshooting')}`;
  }

  function renderSecurity() {
    const s = data.securityCase || {};
    $('#securityContent').innerHTML = `<div class="section-intro-row"><div><p class="eyebrow">CYBERSECURITY CASE</p><h2>${escapeHtml(s.title || 'Add your security case')}<span class="accent-dot">.</span></h2></div><p class="section-intro">Defensive understanding, responsible practice, and clear communication are the focus of this case study.</p></div>
      <div class="security-grid"><article class="security-main"><span class="security-tag">DEFENSIVE CASE STUDY</span>${detailBlock('1. What is the vulnerability?', s.vulnerability)}${detailBlock('2. How can it happen?', s.howItHappens)}${detailBlock('3. What are the risks?', s.risks)}</article><aside class="security-side">${detailBlock('4. How developers can prevent it', s.prevention)}${detailBlock('5. Security practices', s.practices)}${detailBlock('Safe demonstration', s.demonstration)}</aside></div>`;
  }

  function renderAiLiteracy() {
    const logs = Array.isArray(data.aiLog) ? data.aiLog : [];
    const reflection = data.aiReflection || {};
    $('#aiLiteracyContent').innerHTML = `<div class="section-intro-row"><div><p class="eyebrow">RESPONSIBLE AI USE</p><h2>Use AI thoughtfully. Verify the result<span class="accent-dot">.</span></h2></div><p class="section-intro">The PDF asks you to document the date, task, AI assistance, and your own verification. Be transparent about AI contributions and errors.</p></div>
      <div class="ai-log-wrap"><div class="subsection-heading"><h3>AI Usage Log</h3><button class="text-button" data-open-editor="aiLog">+ Add / edit log</button></div>${logs.length ? `<div class="table-scroll"><table class="portfolio-table"><thead><tr><th>Date</th><th>Task</th><th>AI assistance</th><th>My verification / result</th></tr></thead><tbody>${logs.map((item) => `<tr><td>${escapeHtml(item.date || '—')}</td><td>${multiline(item.task || '')}</td><td>${multiline(item.assistance || '')}</td><td>${multiline(item.verification || '')}<br><span class="table-muted">${multiline(item.result || '')}</span></td></tr>`).join('')}</tbody></table></div>` : emptyState('No AI usage documented', 'Add truthful entries about AI use and what you checked.', 'aiLog')}</div>
      <div class="ai-reflection-grid">${reflectionBlock('What did AI help me accomplish?', reflection.helped)}${reflectionBlock('What did I personally verify?', reflection.verified)}${reflectionBlock('What did I learn?', reflection.learned)}${reflectionBlock('What limitations or errors did I discover?', reflection.limitations)}</div>`;
  }

  function reflectionBlock(title, value) {
    return `<article class="reflection-prompt"><h4>${escapeHtml(title)}</h4><p>${multiline(value || 'Add your reflection in the portfolio data file.')}</p></article>`;
  }

  function renderEmployability() {
    const interviews = Array.isArray(data.interviews) ? data.interviews : [];
    const plan = Array.isArray(data.defensePlan) ? data.defensePlan : [];
    $('#employabilityContent').innerHTML = `<div class="section-intro-row"><div><p class="eyebrow">05 / EMPLOYABILITY</p><h2>Prepare to explain your work<span class="accent-dot">.</span></h2></div><p class="section-intro">Employability evidence includes mock interview preparation, technical communication, and a project defense based on your actual system.</p></div>
      <div class="employability-layout"><div class="interview-panel"><div class="subsection-heading"><h3>Interview preparation</h3><button class="text-button" data-open-editor="interviews">Edit answers</button></div><p class="muted-copy">Use honest examples. These prompts are not meant to be memorized as generic answers.</p>${interviews.length ? interviews.map((item, index) => `<details class="interview-item"><summary><span>${String(index + 1).padStart(2, '0')}</span>${escapeHtml(item.question || 'Interview question')}</summary><p>${multiline(item.answer || 'Write your answer in the portfolio data file.')}</p></details>`).join('') : '<p class="muted-copy">Add your interview questions and answers in the portfolio data file.</p>'}</div>
      <div class="defense-panel"><div class="subsection-heading"><h3>Project defense run sheet</h3><button class="text-button" data-open-editor="defensePlan">Edit run sheet</button></div><p class="muted-copy">Suggested timings follow the PDF. Rehearse your own content and live demonstration.</p>${plan.length ? `<div class="defense-steps">${plan.map((item, index) => `<article class="defense-step"><div class="defense-time">${escapeHtml(item.duration || '')}</div><div><h4>${String(index + 1).padStart(2, '0')} · ${escapeHtml(item.step || 'Step')}</h4><p>${multiline(item.talkingPoints || '')}</p><p class="defense-demo"><strong>Show:</strong> ${multiline(item.demonstration || '')}</p></div></article>`).join('')}</div>` : '<p class="muted-copy">Add presentation steps in the portfolio data file.</p>'}</div></div>`;
  }

  function renderCareerPlan() {
    const c = data.careerPlan || {};
    const rows = [
      ['Target position', c.targetPosition], ['Target IT field', c.targetField], ['Current skills', c.currentSkills], ['Skills to improve', c.skillsToImprove],
      ['Technologies to learn', c.technologies], ['Certifications to consider', c.certifications]
    ];
    const goals = [['6 months', c.sixMonthGoal], ['1 year', c.oneYearGoal], ['3 years', c.threeYearGoal]];
    $('#careerPlanContent').innerHTML = `<div class="section-intro-row"><div><p class="eyebrow">CAREER DEVELOPMENT</p><h2>Build the next steps<span class="accent-dot">.</span></h2></div><button class="btn btn-outline-primary" data-open-editor="careerPlan">Edit career plan</button></div>
      <div class="career-info-grid">${rows.map(([label, value]) => `<article class="career-info-card"><span class="small-label">${escapeHtml(label)}</span><p>${multiline(value || 'Add details in the portfolio data file.')}</p></article>`).join('')}</div>
      <div class="career-goals">${goals.map(([label, value], index) => `<article class="career-goal"><span class="goal-marker">0${index + 1}</span><span class="goal-time">${escapeHtml(label)}</span><p>${multiline(value || 'Set a measurable goal in the portfolio data file.')}</p></article>`).join('')}</div>`;
  }

  function renderResume() {
    const r = data.resume || {};
    const resumeUrl = safeUrl(r.resumeUrl);
    const action = resumeUrl
      ? `<a class="btn btn-primary" href="${escapeHtml(resumeUrl)}" target="_blank" rel="noopener noreferrer">Open / Download Resume ↓</a>`
      : `<a class="btn btn-primary" href="editing.html">Add your resume ↓</a>`;
    $('#resumeContent').innerHTML = `<div class="resume-card"><div class="resume-icon" aria-hidden="true">PDF</div><div class="resume-text"><p class="eyebrow">06 / RESUME</p><h2>A one-page resume, ready to share<span class="accent-dot">.</span></h2><p>Include your professional title, contact details, summary, technical skills, education, projects, certifications, and relevant achievements. Keep every claim consistent with the evidence in this portfolio.</p><div class="resume-actions">${action}<a class="btn btn-outline-primary" href="editing.html">How to update resume</a></div>${r.fileName ? `<p class="file-note">Current file: ${escapeHtml(r.fileName)}</p>` : ''}</div></div>`;
  }
  function renderCertificates() {
    const items = Array.isArray(data.certificates) ? data.certificates : [];
    $('#certificatesContent').innerHTML = `<div class="section-intro-row"><div><p class="eyebrow">07 / CERTIFICATES & ACHIEVEMENTS</p><h2>Evidence of continued learning<span class="accent-dot">.</span></h2></div><button class="btn btn-outline-primary" data-open-editor="certificates">+ Add achievement</button></div>
      ${items.length ? `<div class="cert-grid">${items.map((item) => `<article class="cert-card"><div class="cert-mark">✦</div><div><h3>${escapeHtml(item.name || 'Certificate / achievement')}</h3><p class="cert-issuer">${escapeHtml(item.issuer || 'Issuer not added')}${item.date ? ' · ' + escapeHtml(item.date) : ''}</p><p>${multiline(item.description || '')}</p>${safeUrl(item.credentialUrl) ? `<a class="inline-link" href="${escapeHtml(safeUrl(item.credentialUrl))}" target="_blank" rel="noopener noreferrer">View credential ↗</a>` : '<span class="link-placeholder">Credential link not added</span>'}</div></article>`).join('')}</div>` : emptyState('No certificates or achievements added yet', 'Add only genuine certificates, awards, or accomplishments when you have them.', 'certificates')}`;
  }

  function renderGithub() {
    const p = data.profile;
    const repoLinks = (data.projects || []).filter((project) => safeUrl(project.githubUrl));
    $('#githubContent').innerHTML = `<div class="github-card"><div class="github-mark" aria-hidden="true">GH</div><div class="github-copy"><p class="eyebrow">08 / GITHUB</p><h2>Source code. History. Documentation<span class="accent-dot">.</span></h2><p>Use GitHub to show repositories, commit history, README files, issues, and project documentation. Add a repository for each project where appropriate, and remove secrets or private data before publishing.</p><div class="github-actions">${linkOrPlaceholder(p.github, 'Open GitHub profile', 'btn btn-primary')}${repoLinks.map((project) => linkOrPlaceholder(project.githubUrl, project.title || 'Project repository')).join('')}</div></div></div>`;
  }

  function renderContact() {
    const p = data.profile || {};
    const email = String(p.email || '').trim();
    const contactItems = [];
    if (email.includes('@')) contactItems.push(`<a href="mailto:${escapeHtml(email)}" class="contact-link"><span class="contact-symbol">✉</span><span><small>EMAIL</small><strong>${escapeHtml(email)}</strong></span></a>`);
    if (p.phone) contactItems.push(`<div class="contact-link"><span class="contact-symbol">⌕</span><span><small>PHONE</small><strong>${escapeHtml(p.phone)}</strong></span></div>`);
    if (safeUrl(p.linkedin)) contactItems.push(`<a href="${escapeHtml(safeUrl(p.linkedin))}" target="_blank" rel="noopener noreferrer" class="contact-link"><span class="contact-symbol">in</span><span><small>LINKEDIN</small><strong>Open profile ↗</strong></span></a>`);
    if (safeUrl(p.github)) contactItems.push(`<a href="${escapeHtml(safeUrl(p.github))}" target="_blank" rel="noopener noreferrer" class="contact-link"><span class="contact-symbol">GH</span><span><small>GITHUB</small><strong>Open profile ↗</strong></span></a>`);
    $('#contactContent').innerHTML = `<div class="contact-panel"><div><p class="eyebrow">09 / CONTACT</p><h2>Let's connect<span class="accent-dot">.</span></h2><p>For internship and entry-level opportunities, project questions, or professional networking, contact me using the links below.</p><div class="contact-details">${contactItems.length ? contactItems.join('') : '<p>Professional contact details will be added here.</p>'}</div><p class="form-privacy-note">This is a static portfolio. Contact links open your email application or social profile; messages are not stored on this website.</p></div></div>`;
  }

  function renderReflection() {
    const text = (data.reflection || {}).text || '';
    const count = wordCount(text);
    let status = 'Add your personal reflection and remove the prompt text.';
    if (count >= 500 && count <= 800) status = `${count} words · within the PDF’s 500–800 word range.`;
    else if (count < 500) status = `${count} words · aim for 500–800 words for the final submission.`;
    else status = `${count} words · shorten this to 800 words or fewer.`;
    $('#reflectionContent').innerHTML = `<div class="reflection-card"><div class="section-intro-row"><div><p class="eyebrow">10 / REFLECTION</p><h2>Learning, challenges, and growth<span class="accent-dot">.</span></h2></div><button class="btn btn-outline-primary" data-open-editor="reflection">Edit reflection</button></div><p class="reflection-text">${multiline(text || 'Write your reflection in the portfolio data file.')}</p><div class="word-count-line"><span class="word-count-dot"></span><span>${escapeHtml(status)}</span></div><p class="muted-copy reflection-prompts">Include the PDF prompts: prior knowledge, key learning, most educational project, biggest challenge, growth in skills, improvement areas, desired IT professional identity, and career readiness.</p></div>`;
  }

  const CHECKLIST_STORAGE_KEY = 'bsitIndustryReadyPortfolio.checklist.v1';

function readChecklistProgress() {
    try {
        const saved = JSON.parse(
            localStorage.getItem(CHECKLIST_STORAGE_KEY) || '{}'
        );

        return saved && typeof saved === 'object' && !Array.isArray(saved)
            ? saved
            : {};
    } catch (error) {
        console.warn('Could not read checklist progress.', error);
        return {};
    }
}

function writeChecklistProgress(progress) {
    try {
        localStorage.setItem(
            CHECKLIST_STORAGE_KEY,
            JSON.stringify(progress)
        );
        return true;
    } catch (error) {
        console.error('Could not save checklist progress.', error);
        alert('Your browser could not save checklist progress.');
        return false;
    }
}

function checklistProgressKey(item, index) {
    return String(item && item.item ? item.item : 'checklist-item-' + index);
}


  function renderChecklist() {
    const items = Array.isArray(data.checklist) ? data.checklist : [];
    const savedProgress = readChecklistProgress();

    const checklistItems = items.map((item, index) => {
        const key = checklistProgressKey(item, index);

        const completed = Object.prototype.hasOwnProperty.call(savedProgress, key)
            ? Boolean(savedProgress[key])
            : Boolean(item.completed);

        return { item, index, completed };
    });

    const done = checklistItems.filter(entry => entry.completed).length;
    const percentage = checklistItems.length
        ? Math.round((done / checklistItems.length) * 100)
        : 0;

    $('#checklistContent').innerHTML = `
        <div class="section-intro-row">
            <div>
                <p class="eyebrow">SUBMISSION READINESS</p>
                <h2>Final portfolio checklist<span class="accent-dot">.</span></h2>
            </div>
            <a class="text-button" href="editing.html">Update checklist ↗</a>
        </div>

        <div class="checklist-summary">
            <div>
                <strong>${done} / ${checklistItems.length}</strong>
                <span>requirements marked complete</span>
            </div>

            <div class="progress-track"
                 role="progressbar"
                 aria-valuenow="${percentage}"
                 aria-valuemin="0"
                 aria-valuemax="100"
                 aria-label="Portfolio checklist progress">
                <span style="width:${percentage}%"></span>
            </div>

            <span class="progress-number">${percentage}%</span>
        </div>

        <div class="checklist-grid">
            ${checklistItems.map(({ item, index, completed }) => `
                <label class="checklist-item ${completed ? 'is-complete' : ''}">
                    <input
                        type="checkbox"
                        data-checklist-index="${index}"
                        ${completed ? 'checked' : ''}
                        aria-label="${escapeHtml(item.item || 'Requirement')}"
                    >
                    <span class="custom-check" aria-hidden="true">✓</span>
                    <span>${escapeHtml(item.item || 'Requirement')}</span>
                </label>
            `).join('')}
        </div>

        <p class="muted-copy checklist-note">
            You can tick or untick items anytime. Your progress is saved
            in this browser and remains after refreshing the page.
            It does not sync between different devices or visitors.
            Only mark requirements complete when you have the evidence.
        </p>
    `;
  }

  function emptyState(title, message, editorKey) {
    return `<div class="empty-state"><span class="empty-icon" aria-hidden="true">＋</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p><button class="btn btn-outline-primary" data-open-editor="${escapeHtml(editorKey)}">Open portfolio data file</button></div>`;
  }

  function renderAll() {
    renderHero();
    renderProfile();
    renderSkills();
    renderProjects();
    renderEvidence();
    renderTroubleshooting();
    renderSecurity();
    renderAiLiteracy();
    renderEmployability();
    renderCareerPlan();
    renderResume();
    renderCertificates();
    renderGithub();
    renderContact();
    renderReflection();
    renderChecklist();
    $('#footerName').textContent = data.profile.name || 'Your Name';
    $('#currentYear').textContent = new Date().getFullYear();
  }

  function openEditor(key = 'profile') {
    draft = clone(data);
    activeEditorKey = schemas[key] ? key : 'profile';
    $('#editorModal').classList.add('is-open');
    $('#editorModal').setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    renderEditorTabs();
    renderEditorContent();
  }

  function closeEditor() {
    $('#editorModal').classList.remove('is-open');
    $('#editorModal').setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    draft = null;
  }

  function renderEditorTabs() {
    $('#editorTabs').innerHTML = editorOrder.map((key) => `<button class="editor-tab ${key === activeEditorKey ? 'active' : ''}" data-editor-tab="${key}" aria-current="${key === activeEditorKey ? 'page' : 'false'}"><span>${escapeHtml(schemas[key].label)}</span><span class="tab-chevron">›</span></button>`).join('');
  }

  function fieldMarkup(field, value, index) {
    const fieldValue = value == null ? '' : value;
    const dataAttrs = `data-editor-field="${escapeHtml(field.key)}"${index != null ? ` data-editor-index="${index}"` : ''}`;
    const label = `<label class="editor-label">${escapeHtml(field.label)}</label>`;
    if (field.type === 'textarea') {
      return `<div class="editor-field-wrap wide-field">${label}<textarea class="form-control editor-field" ${dataAttrs} rows="${field.rows || 3}">${escapeHtml(fieldValue)}</textarea></div>`;
    }
    if (field.type === 'select') {
      const options = (field.options || []).map((option) => `<option value="${escapeHtml(option)}" ${String(fieldValue) === option ? 'selected' : ''}>${escapeHtml(option)}</option>`).join('');
      return `<div class="editor-field-wrap">${label}<select class="form-select editor-field" ${dataAttrs}>${options}</select></div>`;
    }
    if (field.type === 'checkbox') {
      return `<div class="editor-field-wrap editor-checkbox-wrap"><label class="editor-check-label"><input type="checkbox" class="editor-field" ${dataAttrs} ${fieldValue ? 'checked' : ''}><span>${escapeHtml(field.label)}</span></label></div>`;
    }
    return `<div class="editor-field-wrap">${label}<input class="form-control editor-field" type="text" value="${escapeHtml(fieldValue)}" ${dataAttrs}></div>`;
  }

  function renderEditorContent() {
    const schema = schemas[activeEditorKey];
    $('#editorSectionTitle').textContent = schema.label;
    $('#editorHelp').textContent = schema.help || '';
    const target = $('#editorContent');
    const value = draft[schema.key];
    if (schema.type === 'object') {
      const formFields = schema.fields.map((field) => fieldMarkup(field, value ? value[field.key] : '', null)).join('');
      const uploadMarkup = activeEditorKey === 'resume' ? `<div class="resume-upload-field"><label for="resumeFile" class="editor-label">Upload resume PDF</label><input id="resumeFile" type="file" class="form-control" accept="application/pdf,.pdf"><p class="form-text">PDF only, preferably under 2 MB. The file is stored in this browser, not uploaded to a server. ${draft.resume && draft.resume.fileName ? `Current file: <strong>${escapeHtml(draft.resume.fileName)}</strong>` : ''}</p>${draft.resume && draft.resume.dataUrl ? '<button type="button" class="btn btn-sm btn-outline-danger" id="removeResumeFile">Remove stored PDF</button>' : ''}</div>` : '';
      target.innerHTML = `<div class="editor-object-form">${formFields}${uploadMarkup}</div>`;
      return;
    }
    const entries = Array.isArray(value) ? value : [];
    target.innerHTML = `<div class="editor-collection-head"><p>${entries.length} item${entries.length === 1 ? '' : 's'}</p><button type="button" class="btn btn-sm btn-primary" id="addEditorItem">+ Add item</button></div>${entries.length ? entries.map((entry, index) => `<details class="editor-entry" ${index === 0 ? 'open' : ''}><summary><span class="editor-entry-title">${escapeHtml(collectionEntryTitle(entry, index, activeEditorKey))}</span><button type="button" class="entry-delete" data-delete-entry="${index}" aria-label="Delete item ${index + 1}" title="Delete item">×</button></summary><div class="editor-entry-fields">${schema.fields.map((field) => fieldMarkup(field, entry[field.key], index)).join('')}</div></details>`).join('') : `<div class="editor-empty">No items yet. Use “Add item” to create the first one.</div>`}`;
  }

  function collectionEntryTitle(entry, index, key) {
    if (key === 'skills') return entry.skill || entry.category || `Skill ${index + 1}`;
    if (key === 'projects') return entry.title || `Project ${index + 1}`;
    if (key === 'troubleshooting') return entry.title || `Case ${index + 1}`;
    if (key === 'aiLog') return entry.task || `AI log ${index + 1}`;
    if (key === 'interviews') return entry.question || `Interview question ${index + 1}`;
    if (key === 'defensePlan') return entry.step || `Presentation step ${index + 1}`;
    if (key === 'certificates') return entry.name || `Achievement ${index + 1}`;
    if (key === 'checklist') return entry.item || `Requirement ${index + 1}`;
    return entry.title || entry.name || `Item ${index + 1}`;
  }

  function syncEditorField(target) {
    if (!draft || !target.matches('.editor-field')) return;
    const schema = schemas[activeEditorKey];
    const field = target.getAttribute('data-editor-field');
    const newValue = target.type === 'checkbox' ? target.checked : target.value;
    if (schema.type === 'object') {
      if (!draft[schema.key]) draft[schema.key] = {};
      draft[schema.key][field] = newValue;
    } else {
      const index = Number(target.getAttribute('data-editor-index'));
      if (!Array.isArray(draft[schema.key]) || !draft[schema.key][index]) return;
      draft[schema.key][index][field] = newValue;
    }
  }

  function addEditorItem() {
    const schema = schemas[activeEditorKey];
    if (!schema || schema.type !== 'collection') return;
    draft[schema.key].push(clone(schema.create || {}));
    renderEditorContent();
    const entries = $$('.editor-entry', $('#editorContent'));
    if (entries.length) entries[entries.length - 1].open = true;
    const lastField = $('.editor-entry:last-child .editor-field', $('#editorContent'));
    if (lastField) lastField.focus();
  }

  function deleteEditorItem(index) {
    const schema = schemas[activeEditorKey];
    if (!schema || schema.type !== 'collection') return;
    const item = draft[schema.key][index];
    if (!confirm(`Delete “${collectionEntryTitle(item || {}, index, activeEditorKey)}”? This change will be saved when you click Save Changes.`)) return;
    draft[schema.key].splice(index, 1);
    renderEditorContent();
  }

  function saveEditor() {
    if (!draft) return;
    data = draft;
    if (!saveData()) return;
    renderAll();
    closeEditor();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function exportJson() {
    downloadBlob(JSON.stringify(data, null, 2), 'portfolio-content.json', 'application/json;charset=utf-8');
  }

  function exportPublishFile() {
    const content = '/* Generated from the portfolio editor. Keep this file in assets/js/default-data.js */\nwindow.defaultPortfolio = ' + JSON.stringify(data, null, 2) + ';\n';
    downloadBlob(content, 'default-data.js', 'text/javascript;charset=utf-8');
  }

  function downloadBlob(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  function importJson(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const imported = JSON.parse(String(reader.result || ''));
        if (!imported || !imported.profile || !Array.isArray(imported.projects) || !Array.isArray(imported.skills)) {
          throw new Error('The file does not look like a portfolio content backup.');
        }
        if (!confirm('Import this file and replace the current portfolio content? Export a backup first if needed.')) return;
        data = imported;
        if (saveData()) {
          renderAll();
          closeEditor();
          alert('Portfolio content imported. The content is saved in this browser.');
        }
      } catch (error) {
        alert('Could not import this file. Choose a valid portfolio-content.json export. Details: ' + error.message);
      }
    };
    reader.readAsText(file);
  }

  function resetStarterContent() {
    if (!confirm('Reset this browser to the original starter content? Your current edits will be replaced. Export a backup first if needed.')) return;
    data = getStarterData();
    if (saveData()) {
      renderAll();
      openEditor('profile');
    }
  }

  function handleEditorContentClick(event) {
    const addButton = event.target.closest('#addEditorItem');
    if (addButton) { addEditorItem(); return; }
    const deleteButton = event.target.closest('[data-delete-entry]');
    if (deleteButton) { event.preventDefault(); event.stopPropagation(); deleteEditorItem(Number(deleteButton.dataset.deleteEntry)); return; }
    const removeResumeButton = event.target.closest('#removeResumeFile');
    if (removeResumeButton && draft && draft.resume) {
      draft.resume.dataUrl = '';
      draft.resume.fileName = '';
      renderEditorContent();
    }
  }

  function handleResumeFile(event) {
    const file = event.target.files && event.target.files[0];
    if (!file || !draft || !draft.resume) return;
    if (file.type !== 'application/pdf' && !/\.pdf$/i.test(file.name)) {
      alert('Please choose a PDF file.');
      event.target.value = '';
      return;
    }
    if (file.size > 3 * 1024 * 1024) {
      alert('Please use a resume PDF under 3 MB to reduce the chance of browser storage limits.');
      event.target.value = '';
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      draft.resume.dataUrl = String(reader.result || '');
      draft.resume.fileName = file.name;
      const note = $('.resume-upload-field .form-text');
      if (note) note.innerHTML = `Selected: <strong>${escapeHtml(file.name)}</strong>. Click Save Changes to keep it in this browser.`;
    };
    reader.onerror = () => alert('The selected resume could not be read. Please try another PDF.');
    reader.readAsDataURL(file);
  }

  function eventDelegation() {
    document.addEventListener('change', (event) => {
    const checkbox = event.target.closest('input[data-checklist-index]');

    if (!checkbox) return;

    const index = Number(
        checkbox.getAttribute('data-checklist-index')
    );

    const item = Array.isArray(data.checklist)
        ? data.checklist[index]
        : null;

    if (!item || !Number.isInteger(index)) return;

    const progress = readChecklistProgress();

    progress[checklistProgressKey(item, index)] = checkbox.checked;

    if (!writeChecklistProgress(progress)) {
        checkbox.checked = !checkbox.checked;
        return;
    }

    renderChecklist();
});
    document.addEventListener('click', (event) => {
      const editRequest = event.target.closest('[data-open-editor], #openEditorButton');
      if (editRequest) {
        event.preventDefault();
        window.location.href = 'editing.html';
        return;
      }
      if (event.target.closest('#mobileMenuToggle')) {
        const toggle = event.target.closest('#mobileMenuToggle');
        $('#mainNav').classList.toggle('nav-open');
        toggle.setAttribute('aria-expanded', $('#mainNav').classList.contains('nav-open') ? 'true' : 'false');
        return;
      }
      const navLink = event.target.closest('#mainNav a');
      if (navLink) $('#mainNav').classList.remove('nav-open');
    });
  }

  renderAll();
  eventDelegation();
})();
