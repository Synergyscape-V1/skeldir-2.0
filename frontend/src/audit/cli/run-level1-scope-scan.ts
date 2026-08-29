import { runLevel1NegativeScopeScan, assertLevel1RoutesExist } from '../level1NegativeScopeScan';



const result = runLevel1NegativeScopeScan();

const routes = assertLevel1RoutesExist();



console.log(JSON.stringify({ ...result, routes }, null, 2));



if (result.violations.length > 0 || !routes.ok) {

  process.exit(1);

}


