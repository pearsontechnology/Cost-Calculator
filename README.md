<h1 align="center">POD Cost Calculator For Kubernetes<h1>

<h3>
<pre>
Python Version  : 2.7
Database        : InfluxDB
Database Name   : k8s
</pre>

</h3>

<ul>
<li>Configurations Are Stored in <strong>config.cfg</strong> File</li>
<li><strong>influxdb</strong> module used as a database client</li>
<li><strong>ConfigParser</strong> module used for storing/retrieving configuration settings</li>
</ul>

<strong>Measurement/Collection/Table Structure for Filtered Data</strong><br>
<strong>Measurement/Collection/Table Name:  filtered</strong>
<table>
  <tr>
    <th>pod_id</th>
    <th>pod_name</th>
    <th>namespace</th>
    <th>start_time</th>
    <th>end_time</th>
    <th>cpu_limit(vCPUs)</th>
    <th>memory_limit(GB)</th>
  </tr>
  <tr>
    <td>8d9ab782-89ae-11e8-9dc8-08002794e505</td>
    <td>mongodb</td>
    <td>default</td>
    <td>1531831739</td>
    <td>1531839739</td>
    <td>2.0</td>
    <td>1.0</td>
  </tr>
  <tr>
    <td>e86358d0-89ac-11e8-9dc8-08002794e505</td>
    <td>app-server</td>
    <td>pulse-prod</td>
    <td>1531819739</td>
    <td>0</td>
    <td>2.0</td>
    <td>1.0</td>
  </tr>
  <tr>
    <td>972fefa6-850c-11e8-a6ee-08002794e505</td>
    <td>mysql-database-dff23g2</td>
    <td>pulse-dev</td>
    <td>1531829739</td>
    <td>1531839139</td>
    <td>0</td>
    <td>0</td>
  </tr>
  <tr>
    <td>8a57237c-850d-11e8-a6ee-08002794e505</td>
    <td>api-server-fdff23wgv2</td>
    <td>pulse-dev</td>
    <td>1530831711</td>
    <td>1531039132</td>
    <td>0</td>
    <td>2.0</td>
  </tr>
</table>

<ul>
  <li>Memory or CPU Limit 0 Means, CPU or Memory Limit is not set</li>
  <li>End Time is 0 Means, POD is Alive</li>
</ul>
# Cost-Calculator
