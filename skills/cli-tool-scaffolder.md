---
id: cli-tool-scaffolder
file_path: skills/cli-tool-scaffolder.md
name: CLI Tool Scaffolder
category: developer-experience
tags: [cli, commander, yargs, spinners, developer-experience]
author: opencode-core
version: 1.0.0
description: Scaffold interactive command-line interface tools with argument parsing, flags, spinners, and help menus.
---

# CLI Tool Scaffolder

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm
- CLI framework: `npm i commander` or `npm i yargs` (choose one)
- Optional: `npm iora` for spinners, `chalk` for terminal colors, `inquirer` for interactive prompts

## Execution Steps
1. Initialize the project: `npm init -y` and `npm i commander chalkora inquirer`
2. Define the command structure: `program.command('<command>').description('<desc>')` or `yargs.argv._`
3. Add supported flags/options: `--name`, `-e`, `--verbose`, etc., with description and default values
4. Implement argument validation: check required flags, parse types (`string`, `number`, `boolean`), show help on `--help`
5. Add runtime UI enhancements: `ora` spinner for long operations, `chalk` colored output, `inquirer` for confirmation prompts
6. Wire a help command: `program.help()` or `yargs.showHelp()`, and output a `README.md` or `man` page
7. Publish globally or locally: `npm link` for testing, or `npm pack` / publish to npm registry

```javascript
// Commander CLI with spinner and color
const { Command } = require('commander');
const { green, bold } = require('chalk');
const ora = require('ora');

const program = new Command();
program
  .name('my-tool')
  .description('A helpful CLI scaffolder')
  .option('-n, --name <string>', 'name to greet', 'world')
  .option('-v, --verbose', 'enable verbose output')
  .parse();

const args = program.opts();
const spinner = ora(`Hello, ${green(args.name)}!`).start();

setTimeout(() => {
  spinner.stop();
  console.log(bold('Operation completed successfully!'));
}, 1500);

// Access via: node index.js --name Alice --verbose
```