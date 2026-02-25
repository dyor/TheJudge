  async function exportIteration() {
      if (!currentMeta || Object.keys(currentMeta).length === 0) {
          alert("No iteration loaded.");
          return;
      }
      
      let agentsContent = currentMeta.agents;
      if (!agentsContent) {
          try {
              const r = await fetch('/agents_md');
              agentsContent = await r.text();
          } catch(e) {
              agentsContent = 'None';
          }
      }

      const duration = document.getElementById('statDuration').innerText;
      const tokensTotal = document.getElementById('statTokensTotal').innerText;
      const tokensIn = document.getElementById('statTokensIn').innerText;
      const tokensOut = document.getElementById('statTokensOut').innerText;
      const interventionsTotal = document.getElementById('statInterventionsTotal').innerText;
      const interventionsNit = document.getElementById('statInterventionsNit').innerText;
      const interventionsIssue = document.getElementById('statInterventionsIssue').innerText;
      const interventionsPlanned = document.getElementById('statInterventionsPlanned').innerText;

      let md = `# Iteration: ${currentMeta.name || 'Unknown'}\n\n`;
      md += `**Created At:** ${currentMeta.created_at || 'Unknown'}\n`;
      md += `**Baseline Project:** ${currentMeta.baseline_project || 'None'}\n`;
      md += `**Model:** ${currentMeta.model || 'None'}\n\n`;
      
      md += `## Stats\n`;
      md += `* **Time Elapsed:** ${duration}\n`;
      md += `* **Tokens:** ${tokensTotal} (In: ${tokensIn} | Out: ${tokensOut})\n`;
      md += `* **Interventions:** ${interventionsTotal} (Nit: ${interventionsNit} | Issue: ${interventionsIssue} | Planned: ${interventionsPlanned})\n\n`;

      md += `## Task\n${currentMeta.task || 'None'}\n\n`;
      md += `## Plan\n${currentMeta.plan || 'None'}\n\n`;
      md += `## Skills\n${currentMeta.skills || 'None'}\n\n`;
      md += `## Agents\n${agentsContent || 'None'}\n\n`;
      md += `## System Prompt\n${currentMeta.prompt || 'None'}\n\n`;
      md += `## Notes\n${currentMeta.notes || 'None'}\n`;

      showModal(`Export: ${currentMeta.name || 'Iteration'}`, md);
  }
