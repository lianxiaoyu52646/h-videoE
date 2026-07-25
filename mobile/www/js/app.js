async function initApp() {
  await loadDictionary();
  await openDB();
  
  document.getElementById('speakWordBtn')?.addEventListener('click', () => {
    const word = document.querySelector('.word-popover-word')?.textContent;
    if (word) speakWord(word);
  });
  
  document.getElementById('saveWordBtn')?.addEventListener('click', () => {
    const word = document.querySelector('.word-popover-word')?.textContent;
    if (word) toggleSaveWord(word);
  });
  
  document.addEventListener('click', (e) => {
    const popover = document.getElementById('wordPopover');
    if (popover && !popover.classList.contains('hidden') && !popover.contains(e.target)) {
      const readerPaper = document.getElementById('readerPaper');
      if (!readerPaper || !readerPaper.contains(e.target)) {
        hideWordPopover();
      }
    }
  });
  
  window.addEventListener('hashchange', handleHashChange);
  handleHashChange();
  
  showToast('欢迎使用视频英语', 'info');
}

function handleHashChange() {
  const hash = window.location.hash.slice(1);
  
  switch (hash) {
    case 'wordbooks':
      renderWordbooksPage();
      break;
    case 'reader':
      renderReaderPage();
      break;
    case 'practice':
      renderPracticePage();
      break;
    default:
      renderHomePage();
      break;
  }
}

document.addEventListener('DOMContentLoaded', initApp);