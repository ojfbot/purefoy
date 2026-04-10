import { BrowserAutomationClient } from '../client/BrowserAutomationClient.js';
import { createAssertions } from './assertions/index.js';
import { TestSuite } from './TestSuite.js';
import { TestRunner } from './TestRunner.js';
import { SuiteOptions, RunnerConfig } from './types.js';

export function createTestSuite(
  name: string,
  baseUrl: string = 'http://localhost:3022',
  options: SuiteOptions = {}
): {
  suite: TestSuite;
  client: BrowserAutomationClient;
} {
  const client = new BrowserAutomationClient(baseUrl);
  const assertions = createAssertions(client);
  const suite = new TestSuite(name, assertions, options);

  return { suite, client };
}

export function createTestRunner(config: RunnerConfig = {}): TestRunner {
  return new TestRunner(config);
}

export async function runTest(
  suiteName: string,
  testFn: (suite: TestSuite, client: BrowserAutomationClient) => void | Promise<void>,
  options: {
    baseUrl?: string;
    suiteOptions?: SuiteOptions;
    runnerConfig?: RunnerConfig;
  } = {}
) {
  const { suite, client } = createTestSuite(
    suiteName,
    options.baseUrl,
    options.suiteOptions
  );

  await testFn(suite, client);

  const runner = createTestRunner(options.runnerConfig);
  const result = await runner.run(suite);

  return {
    result,
    exitCode: TestRunner.getExitCode(result),
  };
}
